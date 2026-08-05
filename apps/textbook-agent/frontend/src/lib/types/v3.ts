export interface V3InputForm {
	// Setup
	grade_level: string;
	subject: string;
	duration_minutes: number;
	resource_type:
		| 'lesson'
		| 'mini_booklet'
		| 'worksheet'
		| 'quiz'
		| 'exit_ticket'
		| 'practice_set'
		| 'quick_explainer';

	// Step 1
	topic: string;
	subtopics: string[];
	prior_knowledge: string;
	outcome: string;
	struggle: string;

	// Step 2
	learner_level: 'below_grade' | 'on_grade' | 'above_grade' | 'mixed';
	reading_level: 'below_grade' | 'on_grade' | 'above_grade' | 'mixed';
	language_support: 'none' | 'some_ell' | 'many_ell';
	prior_knowledge_level: 'new_topic' | 'some_background' | 'reviewing';

	// Step 3
	free_text: string;
}

export interface V3IntentDrafts {
	outcome_draft: string;
	struggle_draft: string;
	prior_knowledge_draft: string;
}

export interface V3SignalSummary {
	topic: string;
	subtopic: string | null;
	prior_knowledge: string[];
	learner_needs: string[];
	teacher_goal: string;
	inferred_lesson_mode: 'first_exposure' | 'consolidation' | 'repair' | 'retrieval' | 'transfer';
	lesson_mode_confidence: 'low' | 'high';
}

export interface V3VariantSpec {
	label: string;
	group_description: string;
	voice: {
		register_name: 'simple' | 'balanced' | 'formal';
		tone: 'encouraging' | 'neutral' | 'direct';
		notation: string | null;
	};
}

export interface V3StructuralPlanComponent {
	slug: string;
	purpose: string;
}

export interface V3StructuralPlanSection {
	id: string;
	title: string;
	role: string;
	visual_required: boolean;
	transition_note: string | null;
	components: V3StructuralPlanComponent[];
}

export interface V3StructuralPlanQuestion {
	question_id: string;
	section_id: string;
	temperature: 'warm' | 'medium' | 'cold' | 'transfer';
	diagram_required: boolean;
}

export interface V3StructuralPlan {
	// document_contract_version === 2 marks the native whole-lesson path, which routes
	// approval through the chunked teaching-approval gate instead of Builder conversion.
	document_contract_version?: 1 | 2;
	lesson_mode: string;
	lesson_intent: {
		goal: string;
		structure_rationale: string;
	};
	anchor: {
		example: string;
		reuse_scope: string;
	};
	sections: V3StructuralPlanSection[];
	question_plan: V3StructuralPlanQuestion[];
}

export type V3ChunkedPlanStage =
	| 'stage1_running'
	| 'stage1_failed'
	| 'awaiting_review'
	| 'plan_ready'
	| 'stage2_running'
	| 'variants_running'
	| 'stage2_complete'
	| 'assembly_blocked'
	| 'stage2_error'
	| 'blueprint_ready'
	// Native whole-lesson (document_contract_version=2) stages.
	| 'awaiting_teaching_approval'
	| 'planning_forms'
	| 'rejected_by_teacher'
	| 'complete'
	| 'completed'
	| 'unknown';

export interface V3ChunkedPlanState {
	generation_id: string;
	pack_id?: string | null;
	stage: V3ChunkedPlanStage;
	structural_plan: V3StructuralPlan | null;
	section_briefs: Record<string, unknown>;
	failed_sections: string[];
	blueprint_id: string | null;
	execution_started: boolean;
	next_action: string | null;
	display_title?: string | null;
	error?: string | null;
	error_type?: string | null;
	inferred_lesson_mode: V3SignalSummary['inferred_lesson_mode'] | null;
	lesson_mode_confidence: V3SignalSummary['lesson_mode_confidence'] | null;
	variants?: V3VariantSpec[];
	variant_generation_ids?: Record<string, string>;
}

export interface V3ChunkedPlan {
	generation_id: string;
	pack_id?: string | null;
	structural_plan: V3StructuralPlan;
	display_title?: string | null;
	inferred_lesson_mode: V3SignalSummary['inferred_lesson_mode'] | null;
	lesson_mode_confidence: V3SignalSummary['lesson_mode_confidence'] | null;
	variants?: V3VariantSpec[];
	variant_generation_ids?: Record<string, string>;
}

export interface V3ChunkedStatus {
	generation_id: string;
	pack_id?: string | null;
	stage: V3ChunkedPlanStage;
	doc_version: string | null;
	failed_sections: string[];
	blueprint_id: string | null;
	execution_started: boolean;
	next_action: string | null;
	error?: string | null;
	error_type?: string | null;
	variant_generation_ids?: Record<string, string>;
}

export interface V3PackVariant {
	label: string;
	group_description: string;
	generation_id: string | null;
	status: 'pending' | 'running' | 'landed' | 'failed' | 'deleted';
	stage: string;
	document_path: string | null;
	failed_sections: string[];
	issues: string[];
	can_retry: boolean;
}

export interface V3XplorePack {
	pack_id: string;
	coordinator_generation_id: string;
	subject: string;
	topic: string;
	status: 'generating' | 'ready' | 'failed';
	shared_item_count: number;
	variants: V3PackVariant[];
	editor_ready: boolean;
}

export interface V3SectionPlanItem {
	id: string;
	title: string;
	order: number;
	learning_intents?: string[];
	learning_intent: string;
	components: V3ComponentPlan[];
	visual_required: boolean;
}

export interface V3ComponentPlan {
	component_id: string;
	teacher_label: string;
	content_intent: string;
}

export interface V3QuestionPlan {
	id: string;
	difficulty: 'warm' | 'medium' | 'cold' | 'transfer';
	expected_answer: string;
	diagram_required: boolean;
	attaches_to_section_id: string;
	prompt?: string;
}

export interface V3AnchorExample {
	label: string;
	facts: Record<string, string>;
	correct_result: string | null;
	reuse_scope: string;
}

export interface BlueprintPreviewDTO {
	blueprint_id: string;
	resource_type: string;
	title: string;
	template_id: string;
	anchor: V3AnchorExample | null;
	section_plan: V3SectionPlanItem[];
	question_plan: V3QuestionPlan[];
	register_summary: string;
	support_summary: string[];
}

export interface V3GenerationHistoryItem {
	id: string;
	subject: string;
	title: string;
	status: string;
	booklet_status: string;
	section_count: number;
	document_section_count: number;
	template_id: string;
	created_at: string | null;
	completed_at: string | null;
}

export interface V3PlanningArtifactSource {
	kind: string;
	parent_generation_id: string | null;
	parent_blueprint_id: string | null;
	target_resource_type: string | null;
}

export interface V3PlanningArtifact {
	schema_version?: string;
	generation_id?: string;
	blueprint_id?: string;
	template_id?: string;
	source?: V3PlanningArtifactSource;
	derived?: {
		title?: string;
		resource_type?: string;
	};
}

export interface V3GenerationDetail {
	id: string;
	subject: string;
	title: string;
	status: string;
	booklet_status: string;
	template_id: string;
	section_count: number;
	document_section_count: number;
	report_json: Record<string, unknown>;
	blueprint_id?: string | null;
	planning_artifact?: V3PlanningArtifact | null;
	created_at: string | null;
	completed_at: string | null;
}

export type ComponentStatus = 'pending' | 'generating' | 'ready' | 'patched' | 'failed';

export interface CanvasComponent {
	id: string;
	teacher_label: string;
	status: ComponentStatus;
	data: Record<string, unknown> | null;
}

export interface CanvasVisual {
	id: string;
	status: ComponentStatus | 'omitted_quality' | 'flagged_quality';
	mode?: 'diagram' | 'diagram_series' | 'diagram_compare' | 'simulation';
	image_url: string | null;
	frame_index: number | null;
	component_id?: string | null;
	parent_visual_id?: string | null;
	error_message?: string | null;
	qc_reasons?: string[];
	qc_correction_hint?: string | null;
}

export interface CanvasSection {
	id: string;
	title: string;
	teacher_labels: string;
	order: number;
	sectionStatus: SectionAssemblyStatus;
	stage2Preview: {
		componentIntents: { componentId: string; intent: string }[];
		questionPrompts: string[];
		visualSubject: string | null;
	} | null;
	renderable: boolean;
	missingComponents: string[];
	missingVisuals: string[];
	diagnosticWarnings: string[];
	components: CanvasComponent[];
	visual: CanvasVisual | null;
	questions: Array<{
		id: string;
		difficulty: string;
		status: ComponentStatus;
		data: Record<string, unknown> | null;
	}>;
	/** Merged Lectio section fields (section_field → payload) for template render */
	mergedFields: Record<string, unknown>;
}

export type BookletStatus =
	| 'streaming_preview'
	| 'draft_ready'
	| 'draft_with_warnings'
	| 'draft_needs_review'
	| 'final_ready'
	| 'final_with_warnings'
	| 'failed_unusable';

export type SectionAssemblyStatus = 'complete' | 'incomplete' | 'failed' | 'running';

export interface SectionAssemblyDiagnostic {
	section_id: string;
	status: SectionAssemblyStatus;
	renderable: boolean;
	missing_components: string[];
	missing_visuals: string[];
	warnings: string[];
}

export interface V3DraftPack {
	generation_id: string;
	blueprint_id: string;
	template_id: string;
	subject: string;
	status: BookletStatus;
	sections: Record<string, unknown>[];
	visual_blocks?: Array<{
		visual_id: string;
		attaches_to: string;
		frame_index?: number | null;
		mode: 'diagram' | 'diagram_series' | 'diagram_compare' | 'image' | 'simulation';
		image_url?: string | null;
		component_id?: string | null;
		parent_visual_id?: string | null;
		status?: 'ready' | 'failed' | 'omitted_quality' | 'flagged_quality';
		error_message?: string | null;
		qc_reasons?: string[];
		qc_correction_hint?: string | null;
	}>;
	answer_key?: Record<string, unknown> | null;
	warnings: string[];
	section_diagnostics: SectionAssemblyDiagnostic[];
	booklet_issues: Array<Record<string, unknown>>;
}

export interface V3ParentSnapshot {
	generationId: string | null;
	blueprint: BlueprintPreviewDTO | null;
	canvas: CanvasSection[];
	draftPack: V3DraftPack | null;
	finalPack: V3DraftPack | null;
	activePack: V3DraftPack | null;
	bookletStatus: BookletStatus;
	bookletIssues: Array<Record<string, unknown>>;
}

export type V3Stage =
	| 'intent'
	| 'skeleton'
	| 'teaching_review'
	| 'generating'
	| 'fill'
	| 'edit';

export type { V3PackAdapterDiagnostic, V3PackDocument } from '$lib/studio/v3-pack-to-lectio-document';
