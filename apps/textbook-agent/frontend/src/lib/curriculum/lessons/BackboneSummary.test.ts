// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import BackboneSummary from './BackboneSummary.svelte';
import type { LessonBackbone } from '$lib/types/backbone';

afterEach(cleanup);

const backbone: LessonBackbone = {
	anchor: {
		id: 'anchor',
		story: 'A garden bed is 6 m by 4 m.',
		data: { length: 6, width: 4 },
		answer: '24 m2',
		figure_ids: ['f1']
	},
	variants: [
		{ id: 'v1', change: 'Make the bed 8 m by 3 m.', data: { length: 8, width: 3 }, answer: '24 m2', figure_ids: [] }
	],
	figures: [
		{ id: 'f1', purpose: 'Show the bed as a rectangle', must_show: ['length', 'width'], labels_required: ['6 m', '4 m'], data: {} }
	]
};

describe('BackboneSummary', () => {
	it('shows the anchor, variants, and figures read-only', () => {
		render(BackboneSummary, { props: { backbone } });
		expect(screen.getByText('A garden bed is 6 m by 4 m.')).toBeTruthy();
		expect(screen.getAllByText('length').length).toBe(2);
		expect(screen.getAllByText(/24 m2/).length).toBe(2);
		expect(screen.getByText('Make the bed 8 m by 3 m.')).toBeTruthy();
		expect(screen.getByText('f1')).toBeTruthy();
		expect(screen.getByText(/Show the bed as a rectangle/)).toBeTruthy();
		expect(screen.getByText(/length; width/)).toBeTruthy();
		expect(screen.getByText(/6 m, 4 m/)).toBeTruthy();
		expect(screen.queryByRole('button')).toBeNull();
	});

	it('omits empty sections', () => {
		render(BackboneSummary, {
			props: { backbone: { anchor: { ...backbone.anchor, answer: null }, variants: [], figures: [] } }
		});
		expect(screen.queryByText('Variants')).toBeNull();
		expect(screen.queryByText('Figures')).toBeNull();
		expect(screen.queryByText(/Answer:/)).toBeNull();
	});
});
