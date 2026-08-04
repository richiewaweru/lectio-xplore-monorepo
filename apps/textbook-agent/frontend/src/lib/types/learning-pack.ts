export type PackStatus = 'pending' | 'running' | 'complete' | 'failed';
export type ResourcePhase = 'pending' | 'planning' | 'queued' | 'generating' | 'done' | 'failed';

export interface PackLearningPlan {
	objective: string;
	success_criteria: string[];
	prerequisite_skills: string[];
	likely_misconceptions: string[];
	shared_vocabulary: string[];
	shared_examples: string[];
}

export interface ResourcePlan {
	id: string;
	order: number;
	resource_type: string;
	intended_outcome: string;
	label: string;
	purpose: string;
	depth: 'quick' | 'standard' | 'deep';
	supports: string[];
	enabled: boolean;
}

export interface LearningPackPlan {
	pack_id: string;
	learning_job: {
		job: string;
		subject: string;
		topic: string;
		grade_level: string;
		grade_band: string;
		objective: string;
		class_signals: string[];
		assumptions: string[];
		warnings: string[];
		recommended_depth: 'quick' | 'standard' | 'deep';
		inferred_supports: string[];
		inferred_class_profile: Record<string, unknown>;
	};
	pack_learning_plan: PackLearningPlan;
	resources: ResourcePlan[];
	pack_rationale: string;
}

export interface PackGenerateRequest {
	pack_plan: LearningPackPlan;
	learner_context: string;
}

export interface PackGenerateResponse {
	pack_id: string;
	status: PackStatus;
}

export interface ResourceStatus {
	resource_id: string;
	generation_id: string | null;
	label: string;
	resource_type: string;
	status: string;
	phase: ResourcePhase;
}

export interface PackStatusResponse {
	pack_id: string;
	status: PackStatus;
	learning_job_type: string;
	subject: string;
	topic: string;
	resource_count: number;
	completed_count: number;
	current_phase: string | null;
	current_resource_label: string | null;
	resources: ResourceStatus[];
	created_at: string;
	completed_at: string | null;
}
