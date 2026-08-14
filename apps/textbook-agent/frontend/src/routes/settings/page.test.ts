// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	getProfile: vi.fn(),
	goto: vi.fn()
}));

vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('$lib/api/profile', () => ({ getProfile: mocks.getProfile }));
import SettingsPage from './+page.svelte';

const profile = {
	id: 'profile-1',
	user_id: 'user-1',
	teacher_role: 'teacher',
	subjects: ['mathematics', 'physics'],
	default_grade_band: 'high_school',
	default_audience_description: 'Year 10 mixed-ability maths',
	curriculum_framework: 'GCSE AQA',
	classroom_context: 'Limited devices, mixed prior knowledge.',
	planning_goals: 'Better first drafts and more scaffolded practice.',
	school_or_org_name: 'Riverside High',
	delivery_preferences: {
		tone: 'supportive',
		reading_level: 'simple',
		explanation_style: 'concrete-first',
		example_style: 'everyday',
		brevity: 'tight',
		use_visuals: true,
		print_first: true,
		more_practice: true,
		keep_short: false
	},
	created_at: '2026-04-06T00:00:00Z',
	updated_at: '2026-04-06T00:00:00Z'
};

describe('/settings', () => {
	beforeEach(() => {
		Object.values(mocks).forEach((mock) => mock.mockReset());
		mocks.getProfile.mockResolvedValue(profile);
	});

	afterEach(cleanup);

	it('renders the existing profile summary and edit entry point', async () => {
		render(SettingsPage);
		expect(screen.getByRole('link', { name: '← Units' }).getAttribute('href')).toBe('/units');
		expect(await screen.findByRole('heading', { name: 'Teacher Setup' })).toBeTruthy();
		expect(screen.getByText('Year 10 mixed-ability maths')).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'Edit Profile' }));
		expect(mocks.goto).toHaveBeenCalledWith('/onboarding?mode=edit');
	});

	it('does not expose the retired experimental Builder preference', async () => {
		render(SettingsPage);
		await screen.findByRole('heading', { name: 'Teacher Setup' });
		expect(screen.queryByRole('checkbox')).toBeNull();
	});
});
