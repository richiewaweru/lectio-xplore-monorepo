import type { SectionContent } from 'lectio';

export type TeacherRole = 'teacher' | 'tutor' | 'homeschool' | 'instructor';
export type GradeBand = 'primary' | 'middle' | 'high_school' | 'undergraduate' | 'adult';
export type GenerationMode = 'draft' | 'balanced' | 'strict' | 'v3';
export type Tone = 'supportive' | 'neutral' | 'rigorous';
export type ReadingLevel = 'simple' | 'standard' | 'advanced';
export type ExplanationStyle = 'concrete-first' | 'concept-first' | 'balanced';
export type ExampleStyle = 'everyday' | 'academic' | 'exam';
export type Brevity = 'tight' | 'balanced' | 'expanded';
export type SectionRole =
	| 'intro'
	| 'explain'
	| 'practice'
	| 'summary'
	| 'process'
	| 'compare'
	| 'timeline'
	| 'visual'
	| 'discover';

export interface VisualPolicy {
	required: boolean;
	mode: 'svg' | 'image' | 'none';
	intent?: string | null;
	goal?: string | null;
}

export interface PlanningSectionPlan {
	section_id: string;
	title: string;
	position: number;
	role: SectionRole;
	focus: string;
	components: string[];
	visual_policy: VisualPolicy | null;
}

export interface PlanningGenerationSpec {
	subject: string;
	context: string;
	mode: GenerationMode;
	template_id: string;
	preset_id: string;
	sections: PlanningSectionPlan[];
}

export interface User {
	id: string;
	email: string;
	name: string | null;
	picture_url: string | null;
	has_profile: boolean;
	created_at: string;
	updated_at: string;
}

export interface AuthResponse {
	access_token: string;
	token_type: string;
	user: User;
}

export interface TeacherDeliveryPreferences {
	tone: Tone;
	reading_level: ReadingLevel;
	explanation_style: ExplanationStyle;
	example_style: ExampleStyle;
	brevity: Brevity;
	use_visuals: boolean;
	print_first: boolean;
	more_practice: boolean;
	keep_short: boolean;
}

export interface TeacherProfile {
	id: string;
	user_id: string;
	teacher_role: TeacherRole;
	subjects: string[];
	default_grade_band: GradeBand;
	default_audience_description: string;
	curriculum_framework: string;
	classroom_context: string;
	planning_goals: string;
	school_or_org_name: string;
	delivery_preferences: TeacherDeliveryPreferences;
	created_at: string;
	updated_at: string;
}

export interface TeacherProfileUpsertRequest {
	teacher_role: TeacherRole;
	subjects: string[];
	default_grade_band: GradeBand;
	default_audience_description: string;
	curriculum_framework: string;
	classroom_context: string;
	planning_goals: string;
	school_or_org_name: string;
	delivery_preferences: TeacherDeliveryPreferences;
}

export interface OutlineSection {
	section_id: string;
	position: number;
	title: string;
	focus: string;
}

export interface SectionPlan extends OutlineSection {
	role: string | null;
	required_components: string[];
	optional_components: string[];
	interaction_policy: string | null;
	diagram_policy: string | null;
	enrichment_enabled: boolean;
	continuity_notes: string | null;
}

export interface GenerationAccepted {
	generation_id: string;
	status: string;
	events_url: string;
	document_url: string;
	report_url?: string;
	section_count?: number;
	sections_with_visuals?: number;
	subtopics_covered?: string[];
	warning?: string | null;
}

export interface PDFExportRequest {
	school_name: string;
	teacher_name: string;
	date?: string;
	include_toc?: boolean;
	include_answers?: boolean;
}

export interface GenerationHistoryItem {
	id: string;
	subject: string;
	mode: GenerationMode;
	status: 'pending' | 'running' | 'partial' | 'completed' | 'failed';
	error_type: string | null;
	error_code: string | null;
	requested_template_id: string;
	resolved_template_id: string | null;
	requested_preset_id: string;
	resolved_preset_id: string | null;
	section_count: number | null;
	quality_passed: boolean | null;
	generation_time_seconds: number | null;
	created_at: string | null;
	completed_at: string | null;
}

export interface GenerationDetail {
	id: string;
	subject: string;
	context: string;
	mode: GenerationMode;
	status: 'pending' | 'running' | 'partial' | 'completed' | 'failed';
	error: string | null;
	error_type: string | null;
	error_code: string | null;
	requested_template_id: string;
	resolved_template_id: string | null;
	requested_preset_id: string;
	resolved_preset_id: string | null;
	section_count: number | null;
	quality_passed: boolean | null;
	generation_time_seconds: number | null;
	created_at: string | null;
	completed_at: string | null;
	document_path: string | null;
	planning_spec: PlanningGenerationSpec | null;
}

export interface PipelineSectionManifestItem {
	section_id: string;
	title: string;
	position: number;
}

export interface NodeFailureDetail {
	node: string;
	section_id: string;
	timestamp: string;
	error_type: string;
	error_message: string;
	retry_attempt: number;
	will_retry: boolean;
}

export interface FailedSectionEntry {
	section_id: string;
	title: string;
	position: number;
	focus?: string | null;
	bridges_from?: string | null;
	bridges_to?: string | null;
	needs_diagram: boolean;
	visual_placements_count?: number;
	needs_worked_example: boolean;
	failed_at_node: string;
	error_type: string;
	error_summary: string;
	attempt_count: number;
	can_retry: boolean;
	missing_components: string[];
	failure_detail?: NodeFailureDetail | null;
}

export interface GenerationIssue {
	block: string;
	severity: 'blocking' | 'warning';
	message: string;
}

export interface GenerationSectionReport {
	section_id: string;
	passed: boolean;
	issues: GenerationIssue[];
	warnings: string[];
}

export interface PipelinePartialSectionEntry {
	section_id: string;
	template_id: string;
	content: SectionContent;
	status: string;
	visual_mode?: 'svg' | 'image' | null;
	pending_assets: string[];
	updated_at: string;
}

export interface GenerationDocument {
	generation_id: string;
	subject: string;
	context: string;
	mode: GenerationMode;
	template_id: string;
	preset_id: string;
	status: 'pending' | 'running' | 'partial' | 'completed' | 'failed';
	section_manifest: PipelineSectionManifestItem[];
	sections: SectionContent[];
	partial_sections?: PipelinePartialSectionEntry[];
	failed_sections: FailedSectionEntry[];
	qc_reports: GenerationSectionReport[];
	quality_passed: boolean | null;
	error: string | null;
	created_at: string;
	updated_at: string;
	completed_at: string | null;
}

export interface PipelineStartEvent {
	type: 'pipeline_start';
	generation_id: string;
	section_count: number;
	template_id: string;
	preset_id: string;
	started_at: string;
}

export interface SectionStartedEvent {
	type: 'section_started';
	generation_id: string;
	section_id: string;
	title: string;
	position: number;
}

export interface SectionReadyEvent {
	type: 'section_ready';
	generation_id: string;
	section_id: string;
	section: SectionContent;
	completed_sections: number;
	total_sections: number;
}

export interface MediaPlanReadyEvent {
	type: 'media_plan_ready';
	generation_id: string;
	section_id: string;
	slot_count: number;
	planned_at: string;
}

export interface MediaFrameStartedEvent {
	type: 'media_frame_started';
	generation_id: string;
	section_id: string;
	slot_id: string;
	slot_type: string;
	frame_key: string;
	frame_index: number;
	render?: string | null;
	label?: string | null;
	started_at: string;
}

export interface MediaFrameReadyEvent {
	type: 'media_frame_ready';
	generation_id: string;
	section_id: string;
	slot_id: string;
	slot_type: string;
	frame_key: string;
	frame_index: number;
	render?: string | null;
	label?: string | null;
	ready_at: string;
}

export interface MediaFrameFailedEvent {
	type: 'media_frame_failed';
	generation_id: string;
	section_id: string;
	slot_id: string;
	slot_type: string;
	frame_key: string;
	frame_index: number;
	render?: string | null;
	label?: string | null;
	error?: string | null;
	failed_at: string;
}

export interface MediaSlotReadyEvent {
	type: 'media_slot_ready';
	generation_id: string;
	section_id: string;
	slot_id: string;
	slot_type: string;
	ready_frames: number;
	total_frames: number;
	ready_at: string;
}

export interface MediaSlotFailedEvent {
	type: 'media_slot_failed';
	generation_id: string;
	section_id: string;
	slot_id: string;
	slot_type: string;
	ready_frames: number;
	total_frames: number;
	error?: string | null;
	failed_at: string;
}

export interface SectionMediaBlockedEvent {
	type: 'section_media_blocked';
	generation_id: string;
	section_id: string;
	slot_ids: string[];
	reason: string;
	blocked_at: string;
}

export interface SectionPartialEvent {
	type: 'section_partial';
	generation_id: string;
	section_id: string;
	section: SectionContent;
	template_id: string;
	status: string;
	visual_mode?: 'svg' | 'image' | null;
	pending_assets: string[];
	updated_at: string;
}

export interface SectionAssetPendingEvent {
	type: 'section_asset_pending';
	generation_id: string;
	section_id: string;
	pending_assets: string[];
	status: string;
	visual_mode?: 'svg' | 'image' | null;
	updated_at: string;
}

export interface SectionAssetReadyEvent {
	type: 'section_asset_ready';
	generation_id: string;
	section_id: string;
	ready_assets: string[];
	pending_assets: string[];
	visual_mode?: 'svg' | 'image' | null;
	updated_at: string;
}

export interface SectionFinalEvent {
	type: 'section_final';
	generation_id: string;
	section_id: string;
	completed_sections: number;
	total_sections: number;
}

export interface SectionFailedEvent {
	type: 'section_failed';
	generation_id: string;
	section_id: string;
	title: string;
	position: number;
	failed_at_node: string;
	error_type: string;
	error_summary: string;
	focus?: string | null;
	bridges_from?: string | null;
	bridges_to?: string | null;
	needs_diagram: boolean;
	visual_placements_count?: number;
	needs_worked_example: boolean;
	attempt_count: number;
	can_retry: boolean;
	missing_components: string[];
	failure_detail?: NodeFailureDetail | null;
	timestamp: string;
}

export interface QCCompleteEvent {
	type: 'qc_complete';
	generation_id: string;
	passed: number;
	total: number;
}

export interface RuntimeConcurrencyPolicy {
	max_section_concurrency: number;
	max_media_concurrency: number;
	max_qc_concurrency: number;
}

export interface RuntimeTimeoutPolicy {
	curriculum_planner_timeout_seconds: number;
	content_core_timeout_seconds: number;
	content_practice_timeout_seconds: number;
	content_enrichment_timeout_seconds: number;
	content_repair_timeout_seconds: number;
	field_regenerator_timeout_seconds: number;
	qc_timeout_seconds: number;
	media_inner_timeout_seconds: number;
	media_node_budget_seconds: number;
	generation_timeout_base_seconds: number;
	generation_timeout_per_section_seconds: number;
	generation_timeout_cap_seconds: number;
}

export interface RuntimeRetryPolicy {
	max_attempts: number;
	base_delay_seconds: number;
	call_timeout_seconds: number;
	max_rate_limit_delay_seconds: number;
}

export interface RuntimePolicyEvent {
	type: 'runtime_policy';
	generation_id: string;
	mode: GenerationMode;
	generation_timeout_seconds: number;
	generation_max_concurrent_per_user: number;
	max_section_rerenders: number;
	concurrency: RuntimeConcurrencyPolicy;
	timeouts: RuntimeTimeoutPolicy;
	retries: Record<string, RuntimeRetryPolicy>;
	emitted_at: string;
}

export interface RuntimeProgressSnapshot {
	mode: GenerationMode;
	sections_total: number;
	sections_completed: number;
	sections_running: number;
	sections_queued: number;
	media_running: number;
	media_queued: number;
	qc_running: number;
	qc_queued: number;
	retry_running: number;
	retry_queued: number;
}

export interface RuntimeProgressEvent {
	type: 'runtime_progress';
	generation_id: string;
	snapshot: RuntimeProgressSnapshot;
	emitted_at: string;
}

export type ProgressUpdateStage =
	| 'planning'
	| 'generating_section'
	| 'drafting_partial'
	| 'awaiting_assets'
	| 'generating_media'
	| 'generating_image'
	| 'checking_quality'
	| 'repairing'
	| 'finalizing_section'
	| 'finalizing'
	| 'complete'
	| 'failed';

export interface ProgressUpdateEvent {
	type: 'progress_update';
	generation_id: string;
	stage: ProgressUpdateStage;
	label: string;
	section_id?: string | null;
}

export interface CompleteEvent {
	type: 'complete';
	generation_id: string;
	final_status?: 'completed' | 'partial' | 'failed';
	quality_passed?: boolean | null;
	completed_sections?: number | null;
	total_sections?: number | null;
	document_url?: string;
	report_url?: string;
	completed_at: string;
}

export interface ErrorEvent {
	type: 'error';
	generation_id: string;
	message: string;
	report_url?: string;
	completed_at: string;
}

export interface GenerationFailedEvent {
	type: 'generation_failed';
	generation_id: string;
	message: string;
	error_type?: string | null;
	error_code?: string | null;
	report_url?: string;
	completed_at: string;
}

export type GenerationStreamEvent =
	| PipelineStartEvent
	| MediaPlanReadyEvent
	| MediaFrameStartedEvent
	| MediaFrameReadyEvent
	| MediaFrameFailedEvent
	| MediaSlotReadyEvent
	| MediaSlotFailedEvent
	| SectionMediaBlockedEvent
	| SectionStartedEvent
	| SectionPartialEvent
	| SectionAssetPendingEvent
	| SectionAssetReadyEvent
	| SectionFinalEvent
	| SectionReadyEvent
	| SectionFailedEvent
	| QCCompleteEvent
	| RuntimePolicyEvent
	| RuntimeProgressEvent
	| ProgressUpdateEvent
	| CompleteEvent
	| GenerationFailedEvent
	| ErrorEvent;

