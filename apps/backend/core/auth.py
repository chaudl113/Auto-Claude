"""
Authentication helpers for Auto Claude.

Provides centralized authentication token resolution with fallback support
for multiple environment variables, and SDK environment variable passthrough
for custom API endpoints.

Supports two modes:
1. OAuth Mode (default): Uses Claude Code OAuth tokens
2. Proxy Mode: Uses CLIProxyAPI/ProxyPal for multi-account routing
"""

import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Optional

# =============================================================================
# CLIProxyAPI / ProxyPal Configuration
# =============================================================================
# When CLIProxyAPI is enabled (via config file or env var), Auto Claude routes 
# all API calls through CLIProxyAPI instead of requiring Claude Pro/Max OAuth.
#
# Configuration is read from:
#   1. ~/.auto-claude/cliproxy-config.json (preferred, set by UI)
#   2. Environment variables (fallback)
#
# CLIProxyAPI is an OpenAI-compatible proxy that supports multiple providers:
# - Claude (via OAuth or API key)
# - GitHub Copilot (free with GitHub subscription)
# - OpenAI, Gemini, and more
#
# Default endpoint: http://localhost:8317

CLIPROXY_CONFIG_FILE = Path.home() / ".auto-claude" / "cliproxy-config.json"
CLIPROXY_DEFAULT_URL = "http://localhost:8317"
CLIPROXY_DEFAULT_API_KEY = "sk-proxy-default"  # Default API key for local proxy


def _load_cliproxy_config() -> dict:
    """
    Load CLIProxyAPI configuration from JSON file.
    
    Always reads fresh from disk to pick up UI changes.
    
    Returns:
        Config dict with keys: enabled, url, apiKey, modelMappings
    """
    default_config = {
        "enabled": False,
        "url": CLIPROXY_DEFAULT_URL,
        "apiKey": CLIPROXY_DEFAULT_API_KEY,
        "modelMappings": [
            {"source": "opus", "target": "gpt-5.1", "enabled": True},
            {"source": "sonnet", "target": "gpt-5.1", "enabled": True},
            {"source": "haiku", "target": "claude-haiku-4.5", "enabled": True},
        ],
    }
    
    try:
        if CLIPROXY_CONFIG_FILE.exists():
            with open(CLIPROXY_CONFIG_FILE, "r") as f:
                config = json.load(f)
                # Merge with defaults
                return {**default_config, **config}
    except (json.JSONDecodeError, OSError) as e:
        print(f"   - Warning: Failed to load CLIProxy config: {e}")
    
    return default_config


# Default model mappings: Auto-Claude model -> CLIProxyAPI model
# Users can override these via config file or environment variables
DEFAULT_MODEL_MAPPINGS = {
    # Opus models
    "claude-opus-4-5-20251101": "claude-opus-4.5",
    "claude-opus-4-20250514": "claude-opus-4.5",
    # Sonnet models
    "claude-sonnet-4-5-20250929": "claude-sonnet-4.5",
    "claude-sonnet-4-20250514": "claude-sonnet-4.5",
    # Haiku models
    "claude-haiku-4-5-20251001": "claude-haiku-4.5",
}


def is_cliproxy_enabled() -> bool:
    """Check if CLIProxyAPI mode is enabled (from config file or env var)."""
    # First check config file
    config = _load_cliproxy_config()
    if config.get("enabled"):
        return True
    # Fallback to environment variable
    return os.environ.get("CLIPROXY_ENABLED", "").lower() in ("true", "1", "yes")


def get_cliproxy_url() -> str:
    """Get CLIProxyAPI base URL (from config file or env var)."""
    config = _load_cliproxy_config()
    if config.get("url"):
        return config["url"]
    return os.environ.get("CLIPROXY_URL", CLIPROXY_DEFAULT_URL)


def get_cliproxy_api_key() -> str:
    """Get CLIProxyAPI API key (from config file or env var)."""
    config = _load_cliproxy_config()
    if config.get("apiKey"):
        return config["apiKey"]
    return os.environ.get("CLIPROXY_API_KEY", CLIPROXY_DEFAULT_API_KEY)


def get_cliproxy_model_mappings() -> dict[str, str]:
    """
    Get model mappings from config file or environment variables.
    
    Priority:
    1. Config file (modelMappings array)
    2. Environment variables (CLIPROXY_MODEL_OPUS, etc.)
    3. Default mappings
    """
    mappings = DEFAULT_MODEL_MAPPINGS.copy()
    
    # First, load from config file
    config = _load_cliproxy_config()
    config_mappings = config.get("modelMappings", [])
    
    for mapping in config_mappings:
        if not mapping.get("enabled", True):
            continue
        source = mapping.get("source", "")
        target = mapping.get("target", "")
        if source and target:
            # Map source type (opus, sonnet, haiku) to all model variants
            if source == "opus":
                mappings["claude-opus-4-5-20251101"] = target
                mappings["claude-opus-4-20250514"] = target
            elif source == "sonnet":
                mappings["claude-sonnet-4-5-20250929"] = target
                mappings["claude-sonnet-4-20250514"] = target
            elif source == "haiku":
                mappings["claude-haiku-4-5-20251001"] = target
    
    # Then, check environment variables (can override config)
    opus_model = os.environ.get("CLIPROXY_MODEL_OPUS")
    if opus_model:
        mappings["claude-opus-4-5-20251101"] = opus_model
        mappings["claude-opus-4-20250514"] = opus_model
    
    sonnet_model = os.environ.get("CLIPROXY_MODEL_SONNET")
    if sonnet_model:
        mappings["claude-sonnet-4-5-20250929"] = sonnet_model
        mappings["claude-sonnet-4-20250514"] = sonnet_model
    
    haiku_model = os.environ.get("CLIPROXY_MODEL_HAIKU")
    if haiku_model:
        mappings["claude-haiku-4-5-20251001"] = haiku_model
    
    # Check for individual model mappings (CLIPROXY_MODEL_claude-opus-4-5-20251101=...)
    for key, value in os.environ.items():
        if key.startswith("CLIPROXY_MODEL_") and key not in ("CLIPROXY_MODEL_OPUS", "CLIPROXY_MODEL_SONNET", "CLIPROXY_MODEL_HAIKU"):
            model_name = key.replace("CLIPROXY_MODEL_", "")
            mappings[model_name] = value
    
    return mappings


def translate_model_for_cliproxy(model: str) -> str:
    """
    Translate Auto-Claude model name to CLIProxyAPI model name.
    
    Args:
        model: Original model name (e.g., "claude-opus-4-5-20251101")
    
    Returns:
        Translated model name for CLIProxyAPI (e.g., "copilot-claude-opus-4.5")
    """
    if not is_cliproxy_enabled():
        return model
    
    mappings = get_cliproxy_model_mappings()
    translated = mappings.get(model, model)
    
    if translated != model:
        print(f"   - Model mapping: {model} -> {translated}")
    
    return translated


# Priority order for auth token resolution
# NOTE: We intentionally do NOT fall back to ANTHROPIC_API_KEY.
# Auto Claude is designed to use Claude Code OAuth tokens only.
# This prevents silent billing to user's API credits when OAuth fails.
AUTH_TOKEN_ENV_VARS = [
    "CLAUDE_CODE_OAUTH_TOKEN",  # OAuth token from Claude Code CLI
    "ANTHROPIC_AUTH_TOKEN",  # CCR/proxy token (for enterprise setups)
]

# Environment variables to pass through to SDK subprocess
# NOTE: ANTHROPIC_API_KEY is intentionally excluded to prevent silent API billing
SDK_ENV_VARS = [
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "NO_PROXY",
    "DISABLE_TELEMETRY",
    "DISABLE_COST_WARNINGS",
    "API_TIMEOUT_MS",
]


def get_token_from_keychain() -> Optional[str]:
    """
    Get authentication token from macOS Keychain.

    Reads Claude Code credentials from macOS Keychain and extracts the OAuth token.
    Only works on macOS (Darwin platform).

    Returns:
        Token string if found in Keychain, None otherwise
    """
    # Only attempt on macOS
    if platform.system() != "Darwin":
        return None

    try:
        # Query macOS Keychain for Claude Code credentials
        result = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s",
                "Claude Code-credentials",
                "-w",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return None

        # Parse JSON response
        credentials_json = result.stdout.strip()
        if not credentials_json:
            return None

        data = json.loads(credentials_json)

        # Extract OAuth token from nested structure
        token = data.get("claudeAiOauth", {}).get("accessToken")

        if not token:
            return None

        # Validate token format (Claude OAuth tokens start with sk-ant-oat01-)
        if not token.startswith("sk-ant-oat01-"):
            return None

        return token

    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, Exception):
        # Silently fail - this is a fallback mechanism
        return None


def get_auth_token() -> Optional[str]:
    """
    Get authentication token from environment variables or macOS Keychain.

    Checks multiple sources in priority order:
    1. CLAUDE_CODE_OAUTH_TOKEN (env var)
    2. ANTHROPIC_AUTH_TOKEN (CCR/proxy env var for enterprise setups)
    3. macOS Keychain (if on Darwin platform)

    NOTE: ANTHROPIC_API_KEY is intentionally NOT supported to prevent
    silent billing to user's API credits when OAuth is misconfigured.

    Returns:
        Token string if found, None otherwise
    """
    # First check environment variables
    for var in AUTH_TOKEN_ENV_VARS:
        token = os.environ.get(var)
        if token:
            return token

    # Fallback to macOS Keychain
    return get_token_from_keychain()


def get_auth_token_source() -> Optional[str]:
    """Get the name of the source that provided the auth token."""
    # Check environment variables first
    for var in AUTH_TOKEN_ENV_VARS:
        if os.environ.get(var):
            return var

    # Check if token came from macOS Keychain
    if get_token_from_keychain():
        return "macOS Keychain"

    return None


def require_auth_token() -> str:
    """
    Get authentication token or raise ValueError.

    In CLIProxyAPI mode, returns the proxy API key instead of OAuth token.

    Raises:
        ValueError: If no auth token is found in any supported source
    """
    # CLIProxyAPI mode: use proxy API key, no OAuth required
    if is_cliproxy_enabled():
        api_key = get_cliproxy_api_key()
        print(f"   - CLIProxyAPI mode enabled")
        print(f"   - Proxy URL: {get_cliproxy_url()}")
        return api_key

    # Standard OAuth mode
    token = get_auth_token()
    if not token:
        error_msg = (
            "No OAuth token found.\n\n"
            "Auto Claude requires Claude Code OAuth authentication.\n"
            "Direct API keys (ANTHROPIC_API_KEY) are not supported.\n\n"
            "Alternative: Enable CLIProxyAPI mode by setting:\n"
            "  CLIPROXY_ENABLED=true\n"
            "  CLIPROXY_URL=http://localhost:8317\n\n"
        )
        # Provide platform-specific guidance
        if platform.system() == "Darwin":
            error_msg += (
                "To authenticate with OAuth:\n"
                "  1. Run: claude setup-token\n"
                "  2. The token will be saved to macOS Keychain automatically\n\n"
                "Or set CLAUDE_CODE_OAUTH_TOKEN in your .env file."
            )
        else:
            error_msg += (
                "To authenticate with OAuth:\n"
                "  1. Run: claude setup-token\n"
                "  2. Set CLAUDE_CODE_OAUTH_TOKEN in your .env file"
            )
        raise ValueError(error_msg)
    return token


def get_sdk_env_vars() -> dict[str, str]:
    """
    Get environment variables to pass to SDK.

    In CLIProxyAPI mode, automatically sets ANTHROPIC_BASE_URL to proxy endpoint.

    Collects relevant env vars (ANTHROPIC_BASE_URL, etc.) that should
    be passed through to the claude-agent-sdk subprocess.

    Returns:
        Dict of env var name -> value for non-empty vars
    """
    env = {}

    # CLIProxyAPI mode: override ANTHROPIC_BASE_URL to point to proxy
    if is_cliproxy_enabled():
        env["ANTHROPIC_BASE_URL"] = get_cliproxy_url()
        env["ANTHROPIC_AUTH_TOKEN"] = get_cliproxy_api_key()
        env["DISABLE_TELEMETRY"] = "true"
        env["DISABLE_COST_WARNINGS"] = "true"

    # Collect other SDK env vars (may override CLIProxyAPI defaults if explicitly set)
    for var in SDK_ENV_VARS:
        value = os.environ.get(var)
        if value:
            env[var] = value

    return env


def ensure_claude_code_oauth_token() -> None:
    """
    Ensure CLAUDE_CODE_OAUTH_TOKEN is set (for SDK compatibility).

    If not set but other auth tokens are available, copies the value
    to CLAUDE_CODE_OAUTH_TOKEN so the underlying SDK can use it.
    """
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return

    token = get_auth_token()
    if token:
        os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = token
