import { describe, expect, it } from 'vitest';

import {
	googleClientIdMissingMessage,
	resolveClientApiBase,
	resolveDevProxyTarget,
	resolveGoogleClientId
} from '$lib/config/environment';

describe('API config resolution', () => {
	it('uses relative client paths when no API base is configured', () => {
		expect(resolveClientApiBase({})).toBe('');
	});

	it('prefers PUBLIC_API_URL for browser API calls', () => {
		expect(
			resolveClientApiBase({
				PUBLIC_API_URL: 'http://localhost:8001/',
				VITE_API_TARGET: 'http://localhost:8000/'
			})
		).toBe('http://localhost:8001');
	});

	it('falls back to VITE_API_TARGET for browser API calls', () => {
		expect(resolveClientApiBase({ VITE_API_TARGET: 'http://localhost:8001/' })).toBe(
			'http://localhost:8001'
		);
	});

	it('prefers VITE_API_TARGET for the dev proxy target', () => {
		expect(
			resolveDevProxyTarget({
				PUBLIC_API_URL: 'http://localhost:8001/',
				VITE_API_TARGET: 'http://localhost:8002/'
			})
		).toBe('http://localhost:8002');
	});

	it('uses PUBLIC_API_URL for the dev proxy when no explicit VITE target is set', () => {
		expect(resolveDevProxyTarget({ PUBLIC_API_URL: 'http://localhost:8001/' })).toBe(
			'http://localhost:8001'
		);
	});

	it('resolves the Google client id from the frontend env surface', () => {
		expect(
			resolveGoogleClientId({
				VITE_GOOGLE_CLIENT_ID: 'google-client-id.apps.googleusercontent.com'
			})
		).toBe('google-client-id.apps.googleusercontent.com');
	});

	it('prefers PUBLIC_GOOGLE_CLIENT_ID over VITE_GOOGLE_CLIENT_ID', () => {
		expect(
			resolveGoogleClientId({
				PUBLIC_GOOGLE_CLIENT_ID: 'public-google-client-id.apps.googleusercontent.com',
				VITE_GOOGLE_CLIENT_ID: 'vite-google-client-id.apps.googleusercontent.com'
			})
		).toBe('public-google-client-id.apps.googleusercontent.com');
	});

	it('explains the native frontend env file when the Google client id is missing', () => {
		expect(googleClientIdMissingMessage({ port: '5173' })).toContain(
			'PUBLIC_GOOGLE_CLIENT_ID or VITE_GOOGLE_CLIENT_ID in frontend/.env'
		);
	});

	it('explains the repo-root env file for Docker-local sign-in', () => {
		expect(googleClientIdMissingMessage({ port: '3000' })).toContain(
			'GOOGLE_CLIENT_ID in the repo-root .env'
		);
	});
});
