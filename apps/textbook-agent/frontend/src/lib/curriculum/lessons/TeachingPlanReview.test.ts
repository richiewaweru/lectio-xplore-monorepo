// @vitest-environment jsdom
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import TeachingPlanReview from './TeachingPlanReview.svelte';

describe('TeachingPlanReview', () => {
	it('shows pedagogical content apart from review metadata', () => {
		render(TeachingPlanReview, {
			props: {
				plan: {
					revision: 5,
					arc: 'Trace water through a plant.',
					anchor_usage: [{ slot_id: 'orient', usage: 'Observe a covered leaf.' }],
					misconception_focus_ids: ['water-cycle-order'],
					sections: [{ slot_id: 'orient', blocks: [{
						id: 'b1', intent: 'orient', brief: 'Observe a covered leaf.', evidence: 'A relevant observation.',
						evidence_refs: ['source-1'], visual: { mode: 'diagram', purpose: 'Show the water cycle', labels_required: ['evaporation'], required: true }, source_question_ids: ['question-1'], task_mode: 'assessment',
						learner_action: { action: 'read-explanation', target: 'leaf', purpose: 'Notice water.', expected_evidence: 'Explain droplets.', difficulty: 'guided' }
					}]}]
				},
				review: { status: 'pending', revision: 5 },
				identity: { revision: 5, pending_hash_verified: true, pending_content_hash: 'pending-hash' }
			}
		});

		const planRegion = screen.getByRole('region', { name: 'Teaching plan content' });
		const reviewRegion = screen.getByRole('complementary', { name: 'Review metadata' });
		expect(planRegion.textContent).toContain('Trace water through a plant.');
		expect(planRegion.textContent).toContain('Explain droplets.');
		expect(planRegion.textContent).toContain('source-1');
		expect(planRegion.textContent).toContain('Figure planned: Show the water cycle');
		expect(planRegion.textContent).toContain('evaporation');
		expect(reviewRegion.textContent).toContain('Status: pending');
		expect(reviewRegion.textContent).toContain('Revision: 5');
		expect(reviewRegion.textContent).toContain('Verified pending content hash: pending-hash');
		expect(reviewRegion.textContent).not.toContain('Trace water through a plant.');
	});

	it('shows every enriched Teaching Plan field for a v2 draft', () => {
		render(TeachingPlanReview, {
			props: {
				plan: {
					revision: 7,
					contract_version: 2,
					learner_title: 'Follow the evidence of water',
					starting_state: ['Leaves take in water.'],
					target_state: ['Explain how water leaves a plant.'],
					arc: 'Observe, explain, and connect.',
					sections: [
						{
							slot_id: 'orient',
							display_title: 'Notice the droplets',
							entry_state: ['A covered leaf is available.'],
							must_establish: ['Droplets formed on the cover.'],
							avoid_repeating: ['Do not repeat the setup observation.'],
							bridge_from_previous: null,
							exit_state: ['Learners have evidence of water movement.'],
							blocks: [{ id: 'orient-b1', intent: 'observe', brief: 'Inspect the leaf cover.', evidence: 'Names the droplets.' }]
						},
						{
							slot_id: 'explain',
							display_title: 'Explain the change',
							entry_state: ['Learners have observed droplets.'],
							must_establish: ['Water moved from inside the plant.'],
							avoid_repeating: ['Do not repeat the droplet observation.'],
							bridge_from_previous: 'Use the droplets as evidence for an explanation.',
							exit_state: ['Learners can explain the observed change.'],
							blocks: [{ id: 'explain-b1', intent: 'explain', brief: 'Explain where the droplets came from.', evidence: 'Connects the droplets to plant water.' }]
						}
					]
				}
			}
		});

		const content = screen.getByRole('region', { name: 'Teaching plan content' }).textContent;
		for (const value of [
			'Follow the evidence of water', 'Leaves take in water.', 'Explain how water leaves a plant.',
			'Notice the droplets', 'A covered leaf is available.', 'Droplets formed on the cover.',
			'Do not repeat the setup observation.', 'First section; no prior bridge.',
			'Learners have evidence of water movement.', 'Explain the change',
			'Use the droplets as evidence for an explanation.', 'Learners can explain the observed change.',
			'Names the droplets.'
		]) expect(content).toContain(value);
	});

	it('shows verified approved revision and hash beside the plan content', () => {
		render(TeachingPlanReview, {
			props: {
				plan: { revision: 4, arc: 'Teach the pattern.', sections: [{ slot_id: 'practice', blocks: [{ id: 'b1', intent: 'practice', brief: 'Try one example.', evidence: 'A correct example.' }] }] },
				review: { status: 'approved', revision: 5, approved_revision: 4 },
				identity: { revision: 5, approved_revision: 4, approved_hash_verified: true, approved_content_hash: 'approved-hash' }
			}
		});
		const review = screen.getByRole('complementary', { name: 'Review metadata' });
		expect(review.textContent).toContain('Verified approved revision: 4');
		expect(review.textContent).toContain('Approved content hash: approved-hash');
	});
});
