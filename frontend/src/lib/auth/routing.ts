import { isApiError } from '$lib/api/errors';
import type { User } from '$lib/types';

export function resolveLandingRoute(user: User | null): '/login' | '/onboarding' | '/lessons' {
	if (!user) {
		return '/login';
	}

	return user.has_profile ? '/lessons' : '/onboarding';
}

export function getOnboardingRoute(options: { edit?: boolean } = {}): string {
	return options.edit ? '/onboarding?mode=edit' : '/onboarding';
}

export function isOnboardingEditMode(url: URL): boolean {
	return url.searchParams.get('mode') === 'edit';
}

export function resolveOnboardingGuard(user: User | null, editMode: boolean): string | null {
	if (!user) {
		return '/login';
	}

	if (user.has_profile && !editMode) {
		return '/lessons';
	}

	return null;
}

export function shouldRedirectToOnboarding(user: User | null, path: string): boolean {
	if (!user || user.has_profile) {
		return false;
	}

	const safePaths = ['/login', '/onboarding', '/studio'];
	if (path.startsWith('/studio/print/')) {
		return false;
	}
	return !safePaths.some((safePath) => path.startsWith(safePath));
}

export function resolveShellRedirect(user: User | null, path: string): string | null {
	if (!user) {
		return path.startsWith('/login') ? null : '/login';
	}

	if (path === '/') {
		return resolveLandingRoute(user);
	}

	if (shouldRedirectToOnboarding(user, path)) {
		return '/onboarding';
	}

	return null;
}

export async function navigateToLanding(
	user: User,
	navigate: (path: string, options: { replaceState: boolean }) => void | Promise<void>,
	options: {
		getCurrentPath?: () => string;
		hardRedirect?: (path: string) => void;
	} = {}
): Promise<string> {
	const destination = resolveLandingRoute(user);
	await navigate(destination, { replaceState: true });

	if (options.getCurrentPath?.().startsWith('/login')) {
		options.hardRedirect?.(destination);
	}

	return destination;
}

export function resolveDashboardProfileFailure(
	error: unknown,
	options: { hasProfileHint?: boolean } = {}
): { redirectTo?: string; message?: string } {
	if (isApiError(error)) {
		if (error.status === 401) {
			return { redirectTo: '/login' };
		}

		if (error.status === 404) {
			return {
				redirectTo: options.hasProfileHint ? getOnboardingRoute({ edit: true }) : '/onboarding'
			};
		}

		if (error.status >= 500 && options.hasProfileHint) {
			return { redirectTo: getOnboardingRoute({ edit: true }) };
		}

		return { message: error.detail };
	}

	if (error instanceof Error) {
		return { message: error.message };
	}

	return { message: 'Failed to load your profile.' };
}
