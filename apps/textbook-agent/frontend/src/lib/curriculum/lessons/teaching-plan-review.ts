export type TeachingPlanBlockView = {
	id: string;
	intent: string;
	brief: string;
	evidence: string;
	evidence_refs?: string[];
	departure_reason?: string | null;
	source_question_ids?: string[];
	task_mode?: string;
	sourcebook_needs?: string[];
	sourcebook_refs?: string[];
	stimulus_dependencies?: string[];
	learner_action?: {
		action: string;
		target: string;
		purpose: string;
		expected_evidence: string;
		difficulty: string;
	} | null;
};

export type TeachingPlanView = {
	teaching_plan_id?: string | null;
	revision?: number | null;
	contract_version?: 1 | 2;
	arc: string;
	learner_title?: string | null;
	starting_state?: string[] | null;
	target_state?: string[] | null;
	anchor_usage?: Array<{ slot_id: string; usage: string }>;
	misconception_focus_ids?: string[];
	sections?: Array<{
		slot_id: string;
		specific_purpose?: string;
		transition?: string | null;
		display_title?: string | null;
		entry_state?: string[] | null;
		must_establish?: string[] | null;
		avoid_repeating?: string[] | null;
		bridge_from_previous?: string | null;
		exit_state?: string[] | null;
		blocks?: TeachingPlanBlockView[];
	}>;
};

export type TeachingReviewView = {
	status?: string;
	revision?: number;
	approved_revision?: number | null;
};

export type TeachingPlanIdentityView = {
	revision?: number;
	pending_content_hash?: string | null;
	pending_hash_verified?: boolean;
	approved_revision?: number | null;
	approved_content_hash?: string | null;
	approved_hash_verified?: boolean;
};

export type LessonApproachView = {
	teaching_plan?: TeachingPlanView | null;
	teaching_review?: TeachingReviewView | null;
	teaching_plan_identity?: TeachingPlanIdentityView | null;
	teaching_qc?: Array<{ code?: string; message?: string }>;
};

export function hasVisibleTeachingPlan(plan: TeachingPlanView | null | undefined): boolean {
	if (!plan || !plan.arc?.trim()) return false;
	const hasVisibleBlocks = Boolean(
		plan.sections?.some((section) =>
			section.blocks?.some((block) => Boolean(block.brief?.trim() && block.evidence?.trim()))
		)
	);
	if (!hasVisibleBlocks) return false;
	if (plan.contract_version !== 2) return true;
	if (
		!plan.learner_title?.trim() ||
		!hasMeaningfulState(plan.starting_state) ||
		!hasMeaningfulState(plan.target_state) ||
		!plan.sections?.length
	) return false;
	return plan.sections.every((section, index) => {
		const hasCompleteBlocks = Boolean(
			section.blocks?.length &&
			section.blocks.every((block) => block.brief?.trim() && block.evidence?.trim())
		);
		return Boolean(
			section.slot_id?.trim() &&
			hasCompleteBlocks &&
			section.display_title?.trim() &&
			hasMeaningfulState(section.entry_state) &&
			hasMeaningfulState(section.must_establish) &&
			Array.isArray(section.avoid_repeating) &&
			section.avoid_repeating.every((item) => typeof item === 'string' && item.trim()) &&
			hasMeaningfulState(section.exit_state) &&
			(index === 0
				? section.bridge_from_previous == null
				: Boolean(section.bridge_from_previous?.trim()))
		);
	});
}

function hasMeaningfulState(value: string[] | null | undefined): boolean {
	return Boolean(
		Array.isArray(value) &&
		value.length &&
		value.every((item) => typeof item === 'string' && item.trim())
	);
}

export function canApproveTeachingPlan(view: LessonApproachView | null | undefined): boolean {
	const plan = view?.teaching_plan;
	const review = view?.teaching_review;
	const identity = view?.teaching_plan_identity;
	const revision = Number(review?.revision);
	return Boolean(
		hasVisibleTeachingPlan(plan) &&
		String(review?.status || '').toLowerCase() === 'pending' &&
		identity?.pending_hash_verified === true &&
		typeof identity.pending_content_hash === 'string' &&
		identity.pending_content_hash.trim() &&
		Number.isInteger(revision) &&
		plan?.revision === revision &&
		identity.revision === revision
	);
}

export function isVerifiedApprovedTeachingPlan(view: LessonApproachView | null | undefined): boolean {
	const plan = view?.teaching_plan;
	const review = view?.teaching_review;
	const identity = view?.teaching_plan_identity;
	return Boolean(
		hasVisibleTeachingPlan(plan) &&
		String(review?.status || '').toLowerCase() === 'approved' &&
		identity?.approved_hash_verified === true &&
		typeof identity.approved_content_hash === 'string' &&
		identity.approved_content_hash.trim() &&
		Number.isInteger(identity.approved_revision) &&
		plan?.revision === identity.approved_revision &&
		review?.approved_revision === identity.approved_revision
	);
}
