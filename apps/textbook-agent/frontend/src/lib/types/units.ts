export type KnowledgeType = 'procedural' | 'conceptual' | 'factual' | 'evaluative';
export type LessonMode = 'first_exposure' | 'consolidation' | 'repair' | 'retrieval' | 'transfer';

export interface Unit {
	id: string;
	title: string;
	topic: string;
	subject: string;
	grade_level: string;
	curriculum_context: string | null;
	class_notes: string | null;
	destination_objective: string;
	starting_knowledge: string[];
	status: string;
	active_path_version_id: string | null;
	groups_revision: number;
}

export interface UnitCreateInput {
	title: string;
	topic: string;
	subject: string;
	grade_level: string;
	destination_objective: string;
	starting_knowledge: string[];
	curriculum_context?: string | null;
	class_notes?: string | null;
}

export interface ConstructorReadbackInput {
	subject: string;
	grade_level: string;
	raw_text: string;
	correction?: string;
	clarifying_answer?: string;
}

export interface ConstructorReadback {
	title: string;
	topic: string;
	destination_objective: string;
	starting_knowledge: string[];
	curriculum_context: string | null;
	class_notes: string | null;
	clarifying_question: string | null;
}

export interface LegacyUnitWrapper {
	id: string;
	kind: 'legacy_unit';
	legacy_pack_id: string;
	title: string;
	subject: string;
	destination_objective: string;
	status: string;
	resource_count: number;
	completed_count: number;
	created_at: string;
	lesson: { title: string; pack_id: string; generation_ids: string[]; open_href: string };
	computed: true;
	migration_required: false;
}

export interface PathPlannerInput {
	topic: string;
	subject: string;
	grade_level: string;
	destination_objective: string;
	starting_knowledge: string[];
	curriculum_context?: string | null;
	class_notes?: string | null;
}

export interface PathLesson {
	id: string;
	concept_id: string;
	concept_slug: string;
	title: string;
	objective: string;
	objective_hash: string;
	prerequisites: string[];
	external_prerequisites: string[];
	must_establish: string[];
	exclusions: string[];
	primary_knowledge_type: KnowledgeType;
	secondary_demand: KnowledgeType | null;
	knowledge_type_source: string;
	merge_warning: boolean;
	position: number;
	source: string;
	teacher_edited: boolean;
	skipped: boolean;
	revision: number;
	pack_id: string | null;
}

export type MergeVerdict = 'keep_separate' | 'merge_suggested' | 'teacher_decision';

export interface MergeCriticResult {
	lesson_a: string;
	lesson_b: string;
	verdict: MergeVerdict;
	reason: string;
	merged_objective?: string | null;
	diagnostic_cost?: string | null;
	source?: string;
}

export interface UnitPath {
	id: string;
	unit_id: string;
	version: number;
	revision: number;
	status: string;
	generated_by: string;
	merge_critic_results?: MergeCriticResult[];
	prerequisite_risks?: Record<string, unknown>[];
	forward_verified: boolean;
	reaches_destination: boolean;
	completeness_note: string | null;
	approved_at: string | null;
	created_at: string;
	lessons: PathLesson[];
}

export interface PathEditChatResult extends UnitPath {
	note?: string | null;
	issues?: string[];
}

export interface PathVersionSummary {
	id: string;
	version: number;
	revision: number;
	status: 'draft' | 'approved' | 'superseded' | string;
	generated_by: string;
	forward_verified: boolean;
	reaches_destination: boolean;
	risk_count: number;
	approved_at: string | null;
	created_at: string;
}

export type PathLessonState =
	| 'unprepared'
	| 'awaiting_review'
	| 'generating'
	| 'ready'
	| 'warning'
	| 'failed'
	| 'skipped'
	| 'stale';

export interface PathStatusAggregate {
	path_version_id: string;
	path_revision: number;
	counts: Record<PathLessonState, number>;
	lessons: Array<{
		path_lesson_id: string;
		state: PathLessonState;
		generation_id: string | null;
		warnings: string[];
	}>;
}

export interface PreparedLesson {
	generation_id: string;
	path_lesson_id: string;
	objective: string;
	objective_hash: string;
	skeleton_id: string;
	skeleton_version: number;
	slots: string[];
	section_roles: string[];
	status: 'awaiting_review';
	reused: boolean;
	regeneration_reason?: string;
}

export interface PreparedLessonStatus {
	path_lesson_id: string;
	lesson_revision: number;
	generation_id: string | null;
	generation_status: string;
	workflow_stage: string;
	objective_hash: string;
	stale: boolean;
	can_prepare: boolean;
	can_regenerate: boolean;
}

export interface SkeletonSlotPreview {
	slot_id: string;
	role: string;
	purpose: string;
	allowed_components: string[];
	locked: boolean;
	visual_required: boolean;
}

export interface SkeletonDiffEntry {
	operation: 'add' | 'remove' | 'replace' | 'repeat' | 'reorder';
	slot_id: string;
	replacement_slot: string | null;
	toggle_id: string;
	explanation: string;
}

export interface SkeletonBlockingIssue {
	code: 'variant_slot_overflow' | 'skeleton_conflict';
	message: string;
	toggle_id: string;
}

export interface SkeletonVariantShape {
	group_profile: 'support' | 'core' | 'extension';
	support_level: string;
	slots: SkeletonSlotPreview[];
	toggles_applied: string[];
	warnings: string[];
	structural_diff: SkeletonDiffEntry[];
	blocking_issues: SkeletonBlockingIssue[];
}

export interface SkeletonPreview {
	objective: string;
	knowledge_type: KnowledgeType;
	knowledge_type_source: 'deterministic_preview' | 'provided';
	skeleton_id: string;
	skeleton_version: number;
	variants: SkeletonVariantShape[];
}

export interface LessonShapeDeviation {
	id: string;
	skeleton_id: string;
	skeleton_version: number;
	lesson_mode: LessonMode;
	operation: 'insert' | 'remove' | 'replace' | 'reorder';
	target_slot: string;
	replacement_slot: string | null;
	reason: string;
	requested_by: 'model' | 'teacher';
	status: 'pending_teacher' | 'approved' | 'rejected';
	requested_at: string;
	decided_at: string | null;
	decided_by: string | null;
}

export interface LessonShapePreview {
	path_lesson_id: string;
	lesson_revision: number;
	objective: string;
	objective_hash: string;
	concept_id: string;
	scope_exclusions: string[];
	lesson_mode: LessonMode;
	misconception_count: number;
	skeleton_id: string;
	skeleton_version: number;
	canonical: SkeletonVariantShape;
	variants: SkeletonVariantShape[];
	deviations: LessonShapeDeviation[];
	available_slots: string[];
	blocking_issues: Array<SkeletonBlockingIssue & { group_profile: 'support' | 'core' | 'extension' }>;
	can_prepare: boolean;
}

export type ScheduleFeasibilityStatus = 'unplanned' | 'comfortable' | 'tight' | 'overloaded';

export interface ScheduleFeasibility {
	estimated_minutes: number;
	planned_minutes: number | null;
	delta_minutes: number | null;
	status: ScheduleFeasibilityStatus;
}

export interface TeachingPeriodLesson {
	id: string;
	title: string;
	concept_id: string;
	objective: string;
	path_position: number;
	estimated_minutes: number;
}

export interface TeachingPeriod {
	id: string | null;
	title: string;
	position: number;
	planned_minutes: number | null;
	teacher_note: string | null;
	lesson_ids: string[];
	lessons: TeachingPeriodLesson[];
	feasibility: ScheduleFeasibility;
}

export interface TeachingSchedule {
	path_version_id: string;
	path_revision: number;
	schedule_revision: number;
	periods: TeachingPeriod[];
	feasibility: ScheduleFeasibility;
	suggestion?: {
		period_count: number;
		minutes_per_period: number;
		method: string;
	};
}

export type UnitGroupProfile = 'support' | 'core' | 'extension';

export interface UnitGroupVoice {
	register_name: 'simple' | 'balanced' | 'formal';
	tone: 'encouraging' | 'neutral' | 'direct';
	notation: string | null;
}

export interface UnitGroup {
	id: string;
	label: string;
	profile: UnitGroupProfile;
	description: string;
	toggle_profile: {
		support_level: 'high' | 'medium' | 'low';
		declared_toggles: string[];
	};
	voice: UnitGroupVoice;
	position: number;
	revision: number;
}

export interface UnitGroups {
	unit_id: string;
	groups_revision: number;
	groups: UnitGroup[];
}

export type ResourceProjectionType =
	| 'full_lesson'
	| 'homework'
	| 'revision_sheet'
	| 'flashcards'
	| 'quiz'
	| 'answer_key'
	| 'unit_exam';

export interface ResourceComposeInput {
	projection: ResourceProjectionType;
	path_lesson_ids: string[];
	period_ids: string[];
	group_ids: string[];
	component_refs: string[];
	item_ids: string[];
	include_keys: boolean;
	include_support_notes: boolean;
}

export interface ResourceComponentChoice {
	ref: string;
	path_lesson_id: string;
	lesson_title: string;
	group_id: string | null;
	group_label: string;
	section_id: string;
	role: string;
	title: string;
}

export interface ResourceComposition {
	id: string | null;
	unit_id: string;
	path_version_id: string;
	path_version: number;
	path_revision: number;
	projection: ResourceProjectionType;
	status: 'ready' | 'projection_unavailable';
	can_create?: boolean;
	unavailable_reasons?: string[];
	lesson_ids: string[];
	period_ids: string[];
	group_ids: string[];
	selected_component_refs: string[];
	selected_item_ids: string[];
	include_keys?: boolean;
	template_version: string;
	source_snapshots: Array<Record<string, unknown>>;
	available_lessons?: Array<{ id: string; title: string; position: number }>;
	available_periods?: Array<{ id: string; title: string; position: number }>;
	available_groups?: Array<{ id: string; label: string; profile: UnitGroupProfile }>;
	available_components?: ResourceComponentChoice[];
	available_items?: Array<{ id: string; card_id: string; stem: string }>;
	document: Record<string, unknown> & { sections?: Array<Record<string, unknown>> };
	created_at?: string;
}

export type LessonActualStatus = 'established' | 'partial' | 'recovery_needed' | 'not_taught';
export type LessonPace = 'faster' | 'as_planned' | 'slower' | 'not_recorded';

export interface LessonActual {
	id: string;
	unit_id: string;
	path_version_id: string;
	path_lesson_id: string;
	revision: number;
	lesson_revision: number;
	objective_hash: string;
	status: LessonActualStatus;
	taught: boolean;
	pace: LessonPace;
	established_concepts: string[];
	unresolved_misconceptions: string[];
	anchor_used: string | null;
	teacher_note: string | null;
	supersedes_actual_id: string | null;
	recorded_by: string;
	recorded_at: string;
}

export interface MarksOptionCount {
	option_id: string;
	text: string;
	count: number;
	correct: boolean;
	misconception_id: string | null;
}

export interface MarksItemSummary {
	item_id: string;
	stem: string;
	total_count: number;
	option_counts: MarksOptionCount[];
}

export interface MarksSummary {
	path_lesson_id: string;
	group_id: string | null;
	revision: number;
	items: MarksItemSummary[];
	misconceptions: Array<{ misconception_id: string; label: string; count: number }>;
	unclaimed_distractor_count: number;
	advisory: true;
	advisory_note: string;
}
