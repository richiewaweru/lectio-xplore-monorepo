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
	arc: string;
	anchor_usage?: Array<{ slot_id: string; usage: string }>;
	misconception_focus_ids?: string[];
	sections?: Array<{
		slot_id: string;
		specific_purpose?: string;
		transition?: string | null;
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
	return Boolean(
		plan.sections?.some((section) =>
			section.blocks?.some((block) => Boolean(block.brief?.trim() && block.evidence?.trim()))
		)
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
