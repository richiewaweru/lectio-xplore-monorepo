// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { authStore } = vi.hoisted(() => {
	let current = {
		id: 'user-1',
		email: 'teacher@example.com',
		name: 'Alex',
		picture_url: null,
		has_profile: false,
		created_at: '2026-04-06T00:00:00Z',
		updated_at: '2026-04-06T00:00:00Z'
	};
	const subscribers = new Set<(value: typeof current) => void>();

	return {
		authStore: {
			subscribe(callback: (value: typeof current) => void) {
				subscribers.add(callback);
				callback(current);
				return () => subscribers.delete(callback);
			},
			set(value: typeof current) {
				current = value;
				for (const callback of subscribers) {
					callback(current);
				}
			}
		}
	};
});

const { goto } = vi.hoisted(() => ({
	goto: vi.fn()
}));

const { getProfile, createProfile, updateProfile } = vi.hoisted(() => ({
	getProfile: vi.fn(),
	createProfile: vi.fn(),
	updateProfile: vi.fn()
}));

vi.mock('$app/navigation', () => ({
	goto
}));

vi.mock('$app/state', () => ({
	page: {
		url: new URL('http://localhost/onboarding')
	}
}));

vi.mock('$lib/api/auth', () => ({
	fetchCurrentUser: vi.fn()
}));

vi.mock('$lib/api/profile', () => ({
	getProfile,
	createProfile,
	updateProfile
}));

vi.mock('$lib/api/errors', async () => {
	const actual = await vi.importActual<typeof import('$lib/api/errors')>('$lib/api/errors');
	return actual;
});

vi.mock('$lib/auth/routing', async () => {
	const actual = await vi.importActual<typeof import('$lib/auth/routing')>('$lib/auth/routing');
	return actual;
});

vi.mock('$lib/stores/auth', () => ({
	authUser: authStore,
	logout: vi.fn(),
	updateUser: vi.fn()
}));

import OnboardingPage from './+page.svelte';

describe('onboarding recovery mode', () => {
	beforeEach(() => {
		authStore.set({
			id: 'user-1',
			email: 'teacher@example.com',
			name: 'Alex',
			picture_url: null,
			has_profile: false,
			created_at: '2026-04-06T00:00:00Z',
			updated_at: '2026-04-06T00:00:00Z'
		});
		getProfile.mockResolvedValue({
			id: 'profile-1',
			user_id: 'user-1',
			teacher_role: 'teacher',
			subjects: ['mathematics'],
			default_grade_band: 'high_school',
			default_audience_description: 'Year 10 maths',
			curriculum_framework: 'GCSE',
			classroom_context: 'Mixed confidence.',
			planning_goals: 'Stronger first drafts.',
			school_or_org_name: 'Riverside High',
			delivery_preferences: {
				tone: 'supportive',
				reading_level: 'standard',
				explanation_style: 'balanced',
				example_style: 'everyday',
				brevity: 'balanced',
				use_visuals: false,
				print_first: false,
				more_practice: false,
				keep_short: false
			},
			created_at: '2026-04-06T00:00:00Z',
			updated_at: '2026-04-06T00:00:00Z'
		});
		createProfile.mockReset();
		updateProfile.mockReset();
		goto.mockReset();
	});

	afterEach(() => {
		cleanup();
		vi.clearAllMocks();
	});

	it('switches into recovery mode when a profile exists for a stale has_profile user', async () => {
		render(OnboardingPage);

		await waitFor(() => expect(getProfile).toHaveBeenCalled());
		expect(await screen.findByText(/switched into recovery mode/i)).toBeTruthy();
		expect(screen.getByRole('button', { name: /save profile/i })).toBeTruthy();
		expect(createProfile).not.toHaveBeenCalled();
		expect(updateProfile).not.toHaveBeenCalled();
	});
});
