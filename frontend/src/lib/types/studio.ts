import type { GenerationAccepted, GenerationDocument } from './index';

export type StudioState = 'idle' | 'planning' | 'reviewing' | 'generating';
export type GenerationMode = 'draft' | 'balanced' | 'strict';
export type TopicType = 'concept' | 'process' | 'facts' | 'mixed';
export type LearningOutcome =
	| 'understand-why'
	| 'be-able-to-do'
	| 'remember-terms'
	| 'apply-to-new';
export type ClassStyle =
	| 'tries-before-told'
	| 'needs-explanation-first'
	| 'engages-with-visuals'
	| 'responds-to-worked-examples'
	| 'restless-without-activity';
export type LessonFormat = 'printed-booklet' | 'screen-based' | 'both';
export type Tone = 'supportive' | 'neutral' | 'rigorous';
export type ReadingLevel = 'simple' | 'standard' | 'advanced';
export type ExplanationStyle = 'concrete-first' | 'concept-first' | 'balanced';
export type ExampleStyle = 'everyday' | 'academic' | 'exam';
export type Brevity = 'tight' | 'balanced' | 'expanded';
export type ScaffoldLevel = 'high' | 'medium' | 'low';
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
export type VisualIntent =
	| 'explain_structure'
	| 'show_realism'
	| 'demonstrate_process'
	| 'compare_variants';
export type VisualMode = 'image' | 'svg';
export type PlanningStatus = 'draft' | 'reviewed' | 'committed';

export interface TeacherSignals {
	topic_type: TopicType | null;
	learning_outcome: LearningOutcome | null;
	class_style: ClassStyle[];
	format: LessonFormat | null;
}

export interface DeliveryPreferences {
	tone: Tone;
	reading_level: ReadingLevel;
	explanation_style: ExplanationStyle;
	example_style: ExampleStyle;
	brevity: Brevity;
}

export interface TeacherConstraints {
	more_practice: boolean;
	keep_short: boolean;
	use_visuals: boolean;
	print_first: boolean;
}

export interface StudioBriefRequest {
	intent: string;
	audience: string;
	prior_knowledge: string;
	extra_context: string;
	mode: GenerationMode;
	signals: TeacherSignals;
	preferences: DeliveryPreferences;
	constraints: TeacherConstraints;
	forced_template_id?: string;
}

export type UserBriefDraft = StudioBriefRequest;

export interface TemplateAlternative {
	template_id: string;
	template_name: string;
	fit_score: number;
	why_not_chosen: string;
}

export interface TemplateDecision {
	chosen_id: string;
	chosen_name: string;
	rationale: string;
	fit_score: number;
	alternatives: TemplateAlternative[];
}

export interface GenerationDirectives {
	tone_profile: Tone;
	reading_level: ReadingLevel;
	explanation_style: ExplanationStyle;
	example_style: ExampleStyle;
	scaffold_level: ScaffoldLevel;
	brevity: Brevity;
}

export interface VisualPolicy {
	required: boolean;
	intent: VisualIntent | null;
	mode: VisualMode | null;
	goal: string | null;
	style_notes: string | null;
}

export interface SectionGenerationNotes {
	tone_override: string | null;
	brevity_override: Brevity | null;
	explanation_override: string | null;
}

export interface PlanningBlockVisualPlacement {
	block: 'hook' | 'explanation' | 'practice' | 'worked_example';
	slot_type: 'diagram' | 'diagram_series' | 'diagram_compare';
	sizing?: 'full' | 'compact';
	hint?: string;
	problem_indices?: number[] | null;
}

export interface PlanningSectionPlan {
	id: string;
	order: number;
	role: SectionRole;
	title: string;
	objective: string | null;
	focus_note: string | null;
	transition_note?: string | null;
	selected_components: string[];
	visual_policy: VisualPolicy | null;
	generation_notes: SectionGenerationNotes | null;
	rationale: string;
	terms_to_define?: string[];
	terms_assumed?: string[];
	practice_target?: string | null;
	visual_placements?: PlanningBlockVisualPlacement[];
}

export interface PlanningGenerationSpec {
	id: string;
	template_id: string;
	preset_id: string;
	mode: GenerationMode;
	template_decision: TemplateDecision;
	lesson_rationale: string;
	directives: GenerationDirectives;
	committed_budgets: Record<string, number>;
	sections: PlanningSectionPlan[];
	warning: string | null;
	source_brief_id: string;
	source_brief: StudioBriefRequest;
	status: PlanningStatus;
}

export interface PlanDraft {
	template_decision: TemplateDecision | null;
	lesson_rationale: string;
	warning: string | null;
	sections: PlanningSectionPlan[];
	is_complete: boolean;
	error: string | null;
}

export interface StudioTemplateContract {
	id: string;
	name: string;
	family: string;
	intent: string;
	tagline: string;
	reading_style: string | null;
	tags: string[];
	best_for: string[];
	not_ideal_for: string[];
	learner_fit: string[];
	subjects: string[];
	interaction_level: string;
	lesson_flow: string[];
	required_components: string[];
	optional_components: string[];
	always_present: string[];
	available_components: string[];
	component_budget: Record<string, number>;
	max_per_section: Record<string, number>;
	default_behaviours: Record<string, string>;
	section_role_defaults: Partial<Record<SectionRole, string[]>>;
	signal_affinity: {
		topic_type: Partial<Record<TopicType, number>>;
		learning_outcome: Partial<Record<LearningOutcome, number>>;
		class_style: Partial<Record<ClassStyle, number>>;
		format: Partial<Record<LessonFormat, number>>;
	};
	layout_notes: string[];
	responsive_rules: string[];
	print_rules: string[];
	allowed_presets: string[];
	why_this_template_exists: string;
	generation_guidance: Record<string, unknown>;
}

export interface PlanningTemplateSelectedEvent {
	event: 'template_selected';
	data: {
		template_decision: TemplateDecision;
		lesson_rationale: string;
		warning: string | null;
	};
}

export interface PlanningSectionPlannedEvent {
	event: 'section_planned';
	data: {
		section: PlanningSectionPlan;
	};
}

export interface PlanningCompleteEvent {
	event: 'plan_complete';
	data: {
		spec: PlanningGenerationSpec;
	};
}

export interface PlanningErrorEvent {
	event: 'plan_error';
	data: {
		spec: PlanningGenerationSpec;
		warning: string | null;
	};
}

export type PlanningStreamEvent =
	| PlanningTemplateSelectedEvent
	| PlanningSectionPlannedEvent
	| PlanningCompleteEvent
	| PlanningErrorEvent;

export interface StudioGenerationState {
	accepted: GenerationAccepted | null;
	document: GenerationDocument | null;
	connectionBanner: string | null;
}
