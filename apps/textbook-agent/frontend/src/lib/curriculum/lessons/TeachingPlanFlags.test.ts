// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import TeachingPlanFlags from './TeachingPlanFlags.svelte';
import type { TeachingPlanFlag } from './teaching-plan-review';

afterEach(cleanup);

const flags: TeachingPlanFlag[] = [
	{
		code: 'assessment_item_reused',
		severity: 'warning',
		source: 'reviewer',
		message: 'The worked example reuses the approved check scenario.',
		section_ids: ['explain'],
		block_ids: ['b2'],
		repair_instruction: 'Use a different scenario for the worked example.'
	},
	{
		code: 'SECTION_BLOCK_LIMIT',
		severity: 'warning',
		source: 'validator',
		message: 'section exceeds max_blocks_per_section',
		section_ids: ['confront'],
		block_ids: []
	}
];

describe('TeachingPlanFlags', () => {
	it('lists each flag with its location and suggestion as a warning panel', () => {
		render(TeachingPlanFlags, { props: { flags } });
		expect(screen.getByRole('complementary', { name: 'Reviewer notes' })).toBeTruthy();
		expect(screen.getByText('Reviewer notes (2)')).toBeTruthy();
		expect(screen.getByText(/reuses the approved check scenario/)).toBeTruthy();
		expect(screen.getByText('Section: explain · Block: b2')).toBeTruthy();
		expect(screen.getByText(/Use a different scenario/)).toBeTruthy();
		expect(screen.getByText('Section: confront')).toBeTruthy();
		expect(screen.queryByRole('alert')).toBeNull();
	});

	it('renders nothing when there are no flags', () => {
		render(TeachingPlanFlags, { props: { flags: [] } });
		expect(screen.queryByRole('complementary', { name: 'Reviewer notes' })).toBeNull();
	});
});
