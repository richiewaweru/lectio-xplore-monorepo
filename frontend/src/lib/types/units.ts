export type KnowledgeType = 'procedural' | 'conceptual' | 'factual' | 'evaluative';
export type LessonMode = 'first_exposure' | 'consolidation' | 'repair' | 'retrieval' | 'transfer';

export interface Unit {
	id: string;
	title: string;
	topic: string;
	subject: string;
	grade_level: string;
	curriculum_context: string | null;
	destination_objective: string;
	starting_knowledge: string[];
	status: string;
	active_path_version_id: string | null;
}

export interface UnitCreateInput {
	title: string;
	topic: string;
	subject: string;
	grade_level: string;
	destination_objective: string;
	starting_knowledge: string[];
	curriculum_context?: string | null;
}

export interface PathPlannerInput {
	topic: string;
	subject: string;
	grade_level: string;
	destination_objective: string;
	starting_knowledge: string[];
	curriculum_context?: string | null;
	must_include?: string[];
	must_avoid?: string[];
	terminology?: string[];
	notation?: string | null;
	assessment_context?: string | null;
	known_difficulties?: string[];
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

export interface UnitPath {
	id: string;
	unit_id: string;
	version: number;
	status: string;
	generated_by: string;
	merge_critic_results: Record<string, unknown>[];
	prerequisite_risks: Record<string, unknown>[];
	forward_verified: boolean;
	reaches_destination: boolean;
	approved_at: string | null;
	lessons: PathLesson[];
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

export interface SkeletonPreview {
	objective: string;
	knowledge_type: KnowledgeType;
	knowledge_type_source: 'deterministic_preview' | 'provided';
	skeleton_id: string;
	skeleton_version: number;
	variants: {
		group_profile: 'support' | 'core' | 'extension';
		support_level: string;
		slots: SkeletonSlotPreview[];
		toggles_applied: string[];
		warnings: string[];
	}[];
}
