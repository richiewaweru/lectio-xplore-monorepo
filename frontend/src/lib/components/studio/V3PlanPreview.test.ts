import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import V3PlanPreview from './V3PlanPreview.svelte';

describe('V3PlanPreview', () => {
	it('renders structural plan details', () => {
		render(V3PlanPreview, {
			props: {
				plan: {
					lesson_mode: 'first_exposure',
					lesson_intent: {
						goal: 'By the end students can compare fractions.',
						structure_rationale: 'Start concrete then move symbolic.'
					},
					anchor: {
						example: 'splitting a pizza into 8 equal slices',
						reuse_scope: 'used in intro and practice'
					},
					sections: [
						{
							id: 'intro',
							title: 'Intro',
							role: 'intro',
							visual_required: false,
							transition_note: null,
							components: [{ slug: 'hook-hero', purpose: 'surface anchor' }]
						}
					],
					question_plan: [
						{
							question_id: 'q1',
							section_id: 'intro',
							temperature: 'warm',
							diagram_required: false
						}
					]
				}
			}
		});

		expect(screen.getByText('Structural plan')).toBeTruthy();
		expect(screen.getByText(/splitting a pizza/i)).toBeTruthy();
		expect(screen.getByText('1. Intro')).toBeTruthy();
		expect(screen.getByText(/q1\s*→\s*intro/i)).toBeTruthy();
	});
});
