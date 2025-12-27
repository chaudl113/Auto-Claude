/**
 * Rate limit detection utility for Claude CLI/SDK calls.
 * Detects rate limit errors in stdout/stderr output and provides context.
 */

import { getClaudeProfileManager } from './claude-profile-manager';

/**
 * Regex pattern to detect Claude Code rate limit messages
 * Matches: "Limit reached · resets Dec 17 at 6am (Europe/Oslo)"
 */
const RATE_LIMIT_PATTERN = /Limit reached\s*[·•]\s*resets\s+(.+?)(?:\s*$|\n)/im;

/**
 * Regex pattern to detect JSON error format
 * Matches: {"error":{"type":"usage_limit_reached","message":"The usage limit has been reached",...}}
 */
const JSON_ERROR_PATTERN = /\{\s*"error"\s*:\s*\{[^}]*"type"\s*:\s*"usage_limit_reached"/i;

/**
 * Additional patterns that might indicate rate limiting
 */
const RATE_LIMIT_INDICATORS = [
  /rate\s*limit/i,
  /usage\s*limit/i,
  /limit\s*reached/i,
  /exceeded.*limit/i,
  /too\s*many\s*requests/i
];

/**
 * Patterns that indicate authentication failures
 * These patterns detect when Claude CLI/SDK fails due to missing or invalid auth
 */
const AUTH_FAILURE_PATTERNS = [
  /authentication\s*(is\s*)?required/i,
  /not\s*(yet\s*)?authenticated/i,
  /login\s*(is\s*)?required/i,
  /oauth\s*token\s*(is\s*)?(invalid|expired|missing)/i,
  /unauthorized/i,
  /please\s*(log\s*in|login|authenticate)/i,
  /invalid\s*(credentials|token|api\s*key)/i,
  /auth(entication)?\s*(failed|error|failure)/i,
  /session\s*(expired|invalid)/i,
  /access\s*denied/i,
  /permission\s*denied/i,
  /401\s*unauthorized/i,
  /credentials\s*(are\s*)?(missing|invalid|expired)/i
];

/**
 * Result of rate limit detection
 */
export interface RateLimitDetectionResult {
  /** Whether a rate limit was detected */
  isRateLimited: boolean;
  /** The reset time string if detected (e.g., "Dec 17 at 6am (Europe/Oslo)") */
  resetTime?: string;
  /** Type of limit: 'session' (5-hour) or 'weekly' (7-day) */
  limitType?: 'session' | 'weekly';
  /** The profile ID that hit the limit (if known) */
  profileId?: string;
  /** Best alternative profile to switch to */
  suggestedProfile?: {
    id: string;
    name: string;
  };
  /** Original error message */
  originalError?: string;
  /** JSON error specific fields */
  jsonError?: {
    planType?: string;
    resetsInSeconds?: number;
    resetsAt?: number;
  };
}

/**
 * Result of authentication failure detection
 */
export interface AuthFailureDetectionResult {
  /** Whether an authentication failure was detected */
  isAuthFailure: boolean;
  /** The profile ID that failed to authenticate (if known) */
  profileId?: string;
  /** The type of auth failure detected */
  failureType?: 'missing' | 'invalid' | 'expired' | 'unknown';
  /** User-friendly message describing the failure */
  message?: string;
  /** Original error message from the process output */
  originalError?: string;
}

/**
 * Classify rate limit type based on reset time string
 */
function classifyLimitType(resetTimeStr: string): 'session' | 'weekly' {
  // Weekly limits mention specific dates like "Dec 17" or "Nov 1"
  // Session limits are typically just times like "11:59pm"
  const hasDate = /[A-Za-z]{3}\s+\d+/i.test(resetTimeStr);
  const hasWeeklyIndicator = resetTimeStr.toLowerCase().includes('week');

  return (hasDate || hasWeeklyIndicator) ? 'weekly' : 'session';
}

/**
 * Parse JSON error format and extract rate limit info
 * Expected format: {"error":{"type":"usage_limit_reached","message":"The usage limit has been reached","plan_type":"plus","resets_at":1766860741,"resets_in_seconds":8681}}
 */
function parseJSONError(output: string): RateLimitDetectionResult | null {
  const jsonMatch = output.match(/\{[^{}]*"error"\s*:\s*\{[^}]*\}\s*\}/s);

  if (!jsonMatch) {
    return null;
  }

  try {
    const errorObj = JSON.parse(jsonMatch[0]);

    if (!errorObj.error || errorObj.error.type !== 'usage_limit_reached') {
      return null;
    }

    // Extract reset time from JSON
    const resetsInSeconds = errorObj.error.resets_in_seconds;
    const resetsAt = errorObj.error.resets_at;
    const planType = errorObj.error.plan_type;

    // Calculate human-readable reset time
    let resetTimeStr = '';
    if (resetsInSeconds !== undefined) {
      const hours = Math.floor(resetsInSeconds / 3600);
      const minutes = Math.floor((resetsInSeconds % 3600) / 60);
      const seconds = resetsInSeconds % 60;

      if (hours > 24) {
        const days = Math.floor(hours / 24);
        const remainingHours = hours % 24;
        resetTimeStr = `${days}d ${remainingHours}h`;
      } else if (hours > 0) {
        resetTimeStr = `${hours}h ${minutes}m`;
      } else if (minutes > 0) {
        resetTimeStr = `${minutes}m ${seconds}s`;
      } else {
        resetTimeStr = `${seconds}s`;
      }
    } else if (resetsAt) {
      // Use timestamp if seconds not available
      const resetDate = new Date(resetsAt * 1000);
      resetTimeStr = resetDate.toLocaleString();
    }

    const profileManager = getClaudeProfileManager();
    const effectiveProfileId = profileManager.getActiveProfile().id;

    // Record the rate limit event
    try {
      profileManager.recordRateLimitEvent(effectiveProfileId, resetTimeStr || 'Unknown');
    } catch (err) {
      console.error('[RateLimitDetector] Failed to record rate limit event:', err);
    }

    // Find best alternative profile
    const bestProfile = profileManager.getBestAvailableProfile(effectiveProfileId);

    return {
      isRateLimited: true,
      resetTime: resetTimeStr || 'Unknown',
      limitType: 'weekly', // JSON errors typically indicate weekly limits
      profileId: effectiveProfileId,
      suggestedProfile: bestProfile ? {
        id: bestProfile.id,
        name: bestProfile.name
      } : undefined,
      originalError: output,
      // Add JSON-specific fields
      jsonError: {
        planType,
        resetsInSeconds,
        resetsAt
      }
    };
  } catch (err) {
    console.error('[RateLimitDetector] Failed to parse JSON error:', err);
    return null;
  }
}

/**
 * Detect rate limit from output (stdout + stderr combined)
 */
export function detectRateLimit(
  output: string,
  profileId?: string
): RateLimitDetectionResult {
  // First, check for JSON error format (new format)
  if (JSON_ERROR_PATTERN.test(output)) {
    const jsonDetection = parseJSONError(output);
    if (jsonDetection && jsonDetection.isRateLimited) {
      return jsonDetection;
    }
  }

  // Then check for the primary rate limit pattern (text format)
  const match = output.match(RATE_LIMIT_PATTERN);

  if (match) {
    const resetTime = match[1].trim();
    const limitType = classifyLimitType(resetTime);

    // Record the rate limit event in the profile manager
    const profileManager = getClaudeProfileManager();
    const effectiveProfileId = profileId || profileManager.getActiveProfile().id;

    try {
      profileManager.recordRateLimitEvent(effectiveProfileId, resetTime);
    } catch (err) {
      console.error('[RateLimitDetector] Failed to record rate limit event:', err);
    }

    // Find best alternative profile
    const bestProfile = profileManager.getBestAvailableProfile(effectiveProfileId);

    return {
      isRateLimited: true,
      resetTime,
      limitType,
      profileId: effectiveProfileId,
      suggestedProfile: bestProfile ? {
        id: bestProfile.id,
        name: bestProfile.name
      } : undefined,
      originalError: output
    };
  }

  // Check for secondary rate limit indicators
  for (const pattern of RATE_LIMIT_INDICATORS) {
    if (pattern.test(output)) {
      const profileManager = getClaudeProfileManager();
      const effectiveProfileId = profileId || profileManager.getActiveProfile().id;
      const bestProfile = profileManager.getBestAvailableProfile(effectiveProfileId);

      return {
        isRateLimited: true,
        profileId: effectiveProfileId,
        suggestedProfile: bestProfile ? {
          id: bestProfile.id,
          name: bestProfile.name
        } : undefined,
        originalError: output
      };
    }
  }

  return { isRateLimited: false };
}

/**
 * Check if output contains rate limit error
 */
export function isRateLimitError(output: string): boolean {
  return detectRateLimit(output).isRateLimited;
}

/**
 * Extract reset time from rate limit message
 */
export function extractResetTime(output: string): string | null {
  const match = output.match(RATE_LIMIT_PATTERN);
  return match ? match[1].trim() : null;
}

/**
 * Classify the type of authentication failure based on the error message
 */
function classifyAuthFailureType(output: string): 'missing' | 'invalid' | 'expired' | 'unknown' {
  const lowerOutput = output.toLowerCase();

  if (/missing|not\s*(yet\s*)?authenticated|required/.test(lowerOutput)) {
    return 'missing';
  }
  if (/expired|session\s*expired/.test(lowerOutput)) {
    return 'expired';
  }
  if (/invalid|unauthorized|denied/.test(lowerOutput)) {
    return 'invalid';
  }
  return 'unknown';
}

/**
 * Get a user-friendly message for the authentication failure
 */
function getAuthFailureMessage(failureType: 'missing' | 'invalid' | 'expired' | 'unknown'): string {
  switch (failureType) {
    case 'missing':
      return 'Claude authentication required. Please go to Settings > Claude Profiles and authenticate your account.';
    case 'expired':
      return 'Your Claude session has expired. Please re-authenticate in Settings > Claude Profiles.';
    case 'invalid':
      return 'Invalid Claude credentials. Please check your OAuth token or re-authenticate in Settings > Claude Profiles.';
    case 'unknown':
    default:
      return 'Claude authentication failed. Please verify your authentication in Settings > Claude Profiles.';
  }
}

/**
 * Detect authentication failure from output (stdout + stderr combined)
 */
export function detectAuthFailure(
  output: string,
  profileId?: string
): AuthFailureDetectionResult {
  // First, make sure this isn't a rate limit error (those should be handled separately)
  if (detectRateLimit(output).isRateLimited) {
    return { isAuthFailure: false };
  }

  // Check for authentication failure patterns
  for (const pattern of AUTH_FAILURE_PATTERNS) {
    if (pattern.test(output)) {
      const profileManager = getClaudeProfileManager();
      const effectiveProfileId = profileId || profileManager.getActiveProfile().id;
      const failureType = classifyAuthFailureType(output);

      return {
        isAuthFailure: true,
        profileId: effectiveProfileId,
        failureType,
        message: getAuthFailureMessage(failureType),
        originalError: output
      };
    }
  }

  return { isAuthFailure: false };
}

/**
 * Check if output contains authentication failure error
 */
export function isAuthFailureError(output: string): boolean {
  return detectAuthFailure(output).isAuthFailure;
}

/**
 * Get environment variables for a specific Claude profile.
 * Uses OAuth token (CLAUDE_CODE_OAUTH_TOKEN) if available, otherwise falls back to CLAUDE_CONFIG_DIR.
 * OAuth tokens are preferred as they provide instant, reliable profile switching.
 * Note: Tokens are decrypted automatically by the profile manager.
 */
export function getProfileEnv(profileId?: string): Record<string, string> {
  const profileManager = getClaudeProfileManager();
  const profile = profileId
    ? profileManager.getProfile(profileId)
    : profileManager.getActiveProfile();

  console.warn('[getProfileEnv] Active profile:', {
    profileId: profile?.id,
    profileName: profile?.name,
    email: profile?.email,
    isDefault: profile?.isDefault,
    hasOAuthToken: !!profile?.oauthToken,
    configDir: profile?.configDir
  });

  if (!profile) {
    console.warn('[getProfileEnv] No profile found, using defaults');
    return {};
  }

  // Prefer OAuth token (instant switching, no browser auth needed)
  // Use profile manager to get decrypted token
  if (profile.oauthToken) {
    const decryptedToken = profileId
      ? profileManager.getProfileToken(profileId)
      : profileManager.getActiveProfileToken();

    if (decryptedToken) {
      console.warn('[getProfileEnv] Using OAuth token for profile:', profile.name);
      return {
        CLAUDE_CODE_OAUTH_TOKEN: decryptedToken
      };
    } else {
      console.warn('[getProfileEnv] Failed to decrypt token for profile:', profile.name);
    }
  }

  // Fallback: If default profile, no env vars needed
  if (profile.isDefault) {
    console.warn('[getProfileEnv] Using default profile (no env vars)');
    return {};
  }

  // Fallback: Use configDir for profiles without OAuth token (legacy)
  if (profile.configDir) {
    console.warn('[getProfileEnv] Using configDir fallback for profile:', profile.name);
    console.warn('[getProfileEnv] WARNING: Profile has no OAuth token. Run "claude setup-token" and save the token to enable instant switching.');
    return {
      CLAUDE_CONFIG_DIR: profile.configDir
    };
  }

  console.warn('[getProfileEnv] Profile has no auth method configured');
  return {};
}

/**
 * Get the active Claude profile ID
 */
export function getActiveProfileId(): string {
  return getClaudeProfileManager().getActiveProfile().id;
}

/**
 * Information about a rate limit event for the UI
 */
export interface SDKRateLimitInfo {
  /** Source of the rate limit (which feature hit it) */
  source: 'changelog' | 'task' | 'roadmap' | 'ideation' | 'title-generator' | 'other';
  /** Project ID if applicable */
  projectId?: string;
  /** Task ID if applicable */
  taskId?: string;
  /** The reset time string */
  resetTime?: string;
  /** Type of limit */
  limitType?: 'session' | 'weekly';
  /** Profile that hit the limit */
  profileId: string;
  /** Profile name for display */
  profileName?: string;
  /** Suggested alternative profile */
  suggestedProfile?: {
    id: string;
    name: string;
  };
  /** When detected */
  detectedAt: Date;
  /** Original error message */
  originalError?: string;

  // Auto-swap information
  /** Whether this rate limit was automatically handled via account swap */
  wasAutoSwapped?: boolean;
  /** Profile that was swapped to (if auto-swapped) */
  swappedToProfile?: {
    id: string;
    name: string;
  };
  /** Why this swap occurred: 'proactive' (before limit) or 'reactive' (after limit hit) */
  swapReason?: 'proactive' | 'reactive';
// JSON error specific fields
/** Plan type from JSON error (e.g., 'plus', 'pro', etc.) */
planType?: string;
/** Reset time in seconds from JSON error */
resetsInSeconds?: number;
/** Unix timestamp when limit resets from JSON error */
resetsAt?: number;
}

/**
 * Create SDK rate limit info object for emitting to UI
 */
export function createSDKRateLimitInfo(
  source: SDKRateLimitInfo['source'],
  detection: RateLimitDetectionResult,
  options?: {
    projectId?: string;
    taskId?: string;
  }
): SDKRateLimitInfo {
  const profileManager = getClaudeProfileManager();
  const profile = detection.profileId
    ? profileManager.getProfile(detection.profileId)
    : profileManager.getActiveProfile();

  return {
    source,
    projectId: options?.projectId,
    taskId: options?.taskId,
    resetTime: detection.resetTime,
    limitType: detection.limitType,
    profileId: detection.profileId || profileManager.getActiveProfile().id,
    profileName: profile?.name,
    suggestedProfile: detection.suggestedProfile,
    detectedAt: new Date(),
    originalError: detection.originalError,
    planType: detection.jsonError?.planType,
    resetsInSeconds: detection.jsonError?.resetsInSeconds,
    resetsAt: detection.jsonError?.resetsAt
  };
}
