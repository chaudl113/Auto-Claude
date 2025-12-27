/**
 * Internationalization constants
 * Available languages and display labels
 */

export type SupportedLanguage = 'en' | 'fr' | 'vi';

export const AVAILABLE_LANGUAGES = [
  { value: 'en' as const, label: 'English', nativeLabel: 'English' },
  { value: 'fr' as const, label: 'French', nativeLabel: 'Français' },
  { value: 'vi' as const, label: 'Vietnamese', nativeLabel: 'Tiếng Việt' }
] as const;

export const DEFAULT_LANGUAGE: SupportedLanguage = 'en';
