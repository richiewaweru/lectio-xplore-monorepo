const E2E_API_BASE_KEY = 'lesson-builder-e2e-api-base';

/** Normalised Textbook Generator API origin (no trailing slash), or empty string. */
export function apiBaseUrl(): string {
	if (typeof sessionStorage !== 'undefined') {
		const override = sessionStorage.getItem(E2E_API_BASE_KEY);
		if (override?.trim()) {
			return override.trim().replace(/\/$/, '');
		}
	}
	const base = import.meta.env.PUBLIC_API_URL;
	return typeof base === 'string' ? base.replace(/\/$/, '') : '';
}

export function googleClientId(): string {
	const id = import.meta.env.PUBLIC_GOOGLE_CLIENT_ID;
	return typeof id === 'string' ? id.trim() : '';
}

/** Browser API key for Google Picker (restrict by HTTP referrer in Cloud Console). */
export function googlePickerApiKey(): string {
	const k = import.meta.env.PUBLIC_GOOGLE_API_KEY;
	return typeof k === 'string' ? k.trim() : '';
}

/**
 * Public origin of the Lesson Builder (for share links).
 * Set PUBLIC_BUILDER_ORIGIN in production if the app is served from a different host than the API.
 */
export function builderPublicOrigin(): string {
	const o = import.meta.env.PUBLIC_BUILDER_ORIGIN;
	if (typeof o === 'string' && o.trim()) {
		return o.trim().replace(/\/$/, '');
	}
	if (typeof window !== 'undefined' && window.location?.origin) {
		return window.location.origin;
	}
	return '';
}
