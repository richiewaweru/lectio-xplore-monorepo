import { describe, expect, it } from 'vitest';

import { ApiError } from '$lib/api/errors';
import type { User } from '$lib/types';

import {
	getOnboardingRoute,
	isOnboardingEditMode,
	navigateToLanding,
	resolveDashboardProfileFailure,
	resolveLandingRoute,
	resolveOnboardingGuard,
	resolveShellRedirect,
	shouldRedirectToOnboarding
} from './routing';

const baseUser: User = {
	id: 'user-1',
	email: 'user@example.com',
	name: 'User',
	picture_url: null,
	has_profile: false,
	created_at: '2026-03-12T00:00:00Z',
	updated_at: '2026-03-12T00:00:00Z'
};

describe('auth routing helpers', () => {
	it('resolves the landing route from auth and profile state', () => {
		expect(resolveLandingRoute(null)).toBe('/login');
		expect(resolveLandingRoute(baseUser)).toBe('/onboarding');
		expect(resolveLandingRoute({ ...baseUser, has_profile: true })).toBe('/units');
	});

	it('guards onboarding access for anonymous and fully onboarded users', () => {
		expect(resolveOnboardingGuard(null, false)).toBe('/login');
		expect(resolveOnboardingGuard({ ...baseUser, has_profile: true }, false)).toBe('/units');
		expect(resolveOnboardingGuard({ ...baseUser, has_profile: true }, true)).toBeNull();
		expect(resolveOnboardingGuard(baseUser, false)).toBeNull();
	});

	it('only uses the shell onboarding redirect on routes that cannot self-heal', () => {
		expect(shouldRedirectToOnboarding(baseUser, '/')).toBe(true);
		expect(shouldRedirectToOnboarding(baseUser, '/lessons')).toBe(true);
		expect(shouldRedirectToOnboarding(baseUser, '/studio')).toBe(false);
		expect(shouldRedirectToOnboarding(baseUser, '/onboarding')).toBe(false);
		expect(shouldRedirectToOnboarding({ ...baseUser, has_profile: true }, '/')).toBe(false);
	});

	it('resolves the root route to the correct post-bootstrap destination', () => {
		expect(resolveShellRedirect(null, '/')).toBe('/login');
		expect(resolveShellRedirect(baseUser, '/')).toBe('/onboarding');
		expect(resolveShellRedirect({ ...baseUser, has_profile: true }, '/')).toBe('/units');
	});

	it('detects onboarding edit mode and builds the edit route', () => {
		expect(getOnboardingRoute()).toBe('/onboarding');
		expect(getOnboardingRoute({ edit: true })).toBe('/onboarding?mode=edit');
		expect(isOnboardingEditMode(new URL('http://localhost/onboarding?mode=edit'))).toBe(true);
		expect(isOnboardingEditMode(new URL('http://localhost/onboarding'))).toBe(false);
	});

	it('distinguishes missing profiles from generic dashboard failures', () => {
		expect(resolveDashboardProfileFailure(new ApiError(404, 'Profile not found'))).toEqual({
			redirectTo: '/onboarding'
		});
		expect(
			resolveDashboardProfileFailure(new ApiError(404, 'Profile not found'), {
				hasProfileHint: true
			})
		).toEqual({
			redirectTo: '/onboarding?mode=edit'
		});
		expect(resolveDashboardProfileFailure(new ApiError(401, 'Invalid or expired token'))).toEqual({
			redirectTo: '/login'
		});
		expect(
			resolveDashboardProfileFailure(new ApiError(500, 'Legacy row mismatch'), {
				hasProfileHint: true
			})
		).toEqual({
			redirectTo: '/onboarding?mode=edit'
		});
		expect(resolveDashboardProfileFailure(new ApiError(500, 'Server exploded'))).toEqual({
			message: 'Server exploded'
		});
	});

	it('hard redirects away from login when client-side navigation does not advance', async () => {
		const navigate = async () => undefined;
		let hardRedirectTarget: string | null = null;

		const destination = await navigateToLanding(
			{ ...baseUser, has_profile: true },
			navigate,
			{
				getCurrentPath: () => '/login',
				hardRedirect: (path) => {
					hardRedirectTarget = path;
				}
			}
		);

		expect(destination).toBe('/units');
		expect(hardRedirectTarget).toBe('/units');
	});
});
