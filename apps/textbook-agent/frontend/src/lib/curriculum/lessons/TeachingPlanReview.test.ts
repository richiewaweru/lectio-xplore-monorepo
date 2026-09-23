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
						evidence_refs: ['source-1'], source_question_ids: ['question-1'], task_mode: 'assessment',
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
		expect(reviewRegion.textContent).toContain('Status: pending');
		expect(reviewRegion.textContent).toContain('Revision: 5');
		expect(reviewRegion.textContent).toContain('Verified pending content hash: pending-hash');
		expect(reviewRegion.textContent).not.toContain('Trace water through a plant.');
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
