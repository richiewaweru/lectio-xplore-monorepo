import { describe, expect, it } from 'vitest';
import {
	canApproveTeachingPlan,
	hasVisibleTeachingPlan,
	isVerifiedApprovedTeachingPlan,
	type LessonApproachView
} from './teaching-plan-review';

const pendingView: LessonApproachView = {
	teaching_plan: {
		teaching_plan_id: 'tp-1',
		revision: 3,
		contract_version: 1,
		arc: 'Trace water through the plant.',
		sections: [{
			slot_id: 'orient',
			blocks: [{ id: 'b1', intent: 'orient', brief: 'Observe a covered leaf.', evidence: 'A relevant observation.' }]
		}]
	},
	teaching_review: { status: 'pending', revision: 3 },
	teaching_plan_identity: { revision: 3, pending_content_hash: 'displayed-hash', pending_hash_verified: true }
};

const pendingV2View: LessonApproachView = {
	...pendingView,
	teaching_plan: {
		...pendingView.teaching_plan!,
		contract_version: 2,
		learner_title: 'Follow the water',
		starting_state: ['A leaf takes in water.'],
		target_state: ['Explain water movement.'],
		sections: [{
			slot_id: 'orient',
			display_title: 'Observe the leaf',
			entry_state: ['A covered leaf is ready.'],
			must_establish: ['Droplets are visible.'],
			avoid_repeating: [],
			bridge_from_previous: null,
			exit_state: ['Learners have an observation.'],
			blocks: [{ id: 'b1', intent: 'orient', brief: 'Observe a covered leaf.', evidence: 'Names a visible change.' }]
		}]
	}
};

describe('Teaching Plan review contract', () => {
	it('does not offer approval for blank, unverifiable, or mismatched review content', () => {
		expect(hasVisibleTeachingPlan({ arc: '', sections: [] })).toBe(false);
		expect(hasVisibleTeachingPlan({ arc: 'An arc without visible lesson content.', sections: [] })).toBe(false);
		expect(canApproveTeachingPlan({ ...pendingView, teaching_plan: { arc: '', revision: 3, sections: [] } })).toBe(false);
		expect(canApproveTeachingPlan({
			...pendingView,
			teaching_plan_identity: { ...pendingView.teaching_plan_identity, pending_hash_verified: false }
		})).toBe(false);
		expect(canApproveTeachingPlan({
			...pendingView,
			teaching_plan_identity: { ...pendingView.teaching_plan_identity, pending_content_hash: '  ' }
		})).toBe(false);
		expect(canApproveTeachingPlan({
			...pendingView,
			teaching_plan_identity: { ...pendingView.teaching_plan_identity, revision: 2 }
		})).toBe(false);
		expect(canApproveTeachingPlan({
			...pendingView,
			teaching_plan: { ...pendingView.teaching_plan!, revision: 2 }
		})).toBe(false);
	});

	it('requires all meaningful v2 content to be visible before approval', () => {
		expect(hasVisibleTeachingPlan(pendingV2View.teaching_plan)).toBe(true);
		expect(canApproveTeachingPlan(pendingV2View)).toBe(true);
		expect(canApproveTeachingPlan({
			...pendingV2View,
			teaching_plan: { ...pendingV2View.teaching_plan!, learner_title: ' ' }
		})).toBe(false);
		expect(canApproveTeachingPlan({
			...pendingV2View,
			teaching_plan: {
				...pendingV2View.teaching_plan!,
				sections: [{ ...pendingV2View.teaching_plan!.sections![0], exit_state: [] }]
			}
		})).toBe(false);
		expect(canApproveTeachingPlan({
			...pendingV2View,
			teaching_plan: {
				...pendingV2View.teaching_plan!,
				sections: [{ ...pendingV2View.teaching_plan!.sections![0], blocks: [] }]
			}
		})).toBe(false);
		expect(canApproveTeachingPlan({
			...pendingV2View,
			teaching_plan: {
				...pendingV2View.teaching_plan!,
				sections: [{ ...pendingV2View.teaching_plan!.sections![0], bridge_from_previous: 'unexpected first bridge' }]
			}
		})).toBe(false);
	});

	it('allows only a verified current pending hash and verifies approved identity separately', () => {
		expect(canApproveTeachingPlan(pendingView)).toBe(true);
		const approved: LessonApproachView = {
			...pendingView,
			teaching_review: { status: 'approved', revision: 4, approved_revision: 3 },
			teaching_plan_identity: {
				revision: 4,
				approved_revision: 3,
				approved_content_hash: 'displayed-hash',
				approved_hash_verified: true
			}
		};
		expect(isVerifiedApprovedTeachingPlan(approved)).toBe(true);
		expect(isVerifiedApprovedTeachingPlan({
			...approved,
			teaching_plan_identity: { ...approved.teaching_plan_identity, approved_hash_verified: false }
		})).toBe(false);
	});
});
