// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import ProfileSetup from './ProfileSetup.svelte';
import type { TeacherProfileUpsertRequest } from '$lib/types';

describe('ProfileSetup', () => {
	afterEach(() => {
		cleanup();
	});

	it('renders teacher-facing sections and submits the default teacher profile shape', async () => {
		const onsubmit = vi.fn();
		render(ProfileSetup, { props: { onsubmit } });

		expect(screen.getByRole('heading', { name: /teacher profile/i })).toBeTruthy();
		expect(screen.getByRole('heading', { name: /default classroom context/i })).toBeTruthy();
		expect(screen.getByRole('heading', { name: /lesson defaults/i })).toBeTruthy();
		expect(screen.getByRole('heading', { name: /product goals/i })).toBeTruthy();

		await fireEvent.click(screen.getByRole('button', { name: /complete setup/i }));

		expect(onsubmit).toHaveBeenCalledWith({
			teacher_role: 'teacher',
			subjects: [],
			default_grade_band: 'high_school',
			default_audience_description: '',
			curriculum_framework: '',
			classroom_context: '',
			planning_goals: '',
			school_or_org_name: '',
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
			}
		});
	});

	it('hydrates teacher defaults, preserves populated values, and submits edits', async () => {
		const onsubmit = vi.fn();
		const initialData: TeacherProfileUpsertRequest = {
			teacher_role: 'tutor',
			subjects: ['mathematics', 'physics'],
			default_grade_band: 'adult',
			default_audience_description: 'Adult reskillers returning to maths after a long break.',
			curriculum_framework: 'Functional Skills',
			classroom_context: 'Mixed confidence, limited device access, strong response to worked examples.',
			planning_goals: 'Faster first drafts and more scaffolded practice.',
			school_or_org_name: 'Northbridge Learning Centre',
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
			}
		};

		render(ProfileSetup, {
			props: {
				onsubmit,
				initialData,
				submitLabel: 'Save Profile'
			}
		});

		expect((screen.getByLabelText(/teaching role/i) as HTMLSelectElement).value).toBe('tutor');
		expect((screen.getByLabelText(/default grade band/i) as HTMLSelectElement).value).toBe(
			'adult'
		);
		expect(screen.getByDisplayValue('Functional Skills')).toBeTruthy();
		expect(screen.getByDisplayValue('Northbridge Learning Centre')).toBeTruthy();
		expect(screen.getByText('mathematics')).toBeTruthy();
		expect(screen.getByText('physics')).toBeTruthy();
		expect(screen.getByDisplayValue(/adult reskillers returning to maths/i)).toBeTruthy();

		await fireEvent.input(screen.getByLabelText(/school or organisation/i), {
			target: { value: 'Updated Academy' }
		});
		await fireEvent.click(screen.getByRole('button', { name: /save profile/i }));

		expect(onsubmit).toHaveBeenCalledWith({
			...initialData,
			school_or_org_name: 'Updated Academy'
		});
	});
});
