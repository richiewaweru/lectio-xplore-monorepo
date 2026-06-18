import { get, writable } from 'svelte/store';

import type {
	PlanDraft,
	PlanningGenerationSpec,
	PlanningSectionPlan,
	StudioGenerationState,
	StudioState,
	StudioTemplateContract,
	TeacherProfile,
	UserBriefDraft
} from '$lib/types';

export function emptyDraft(): UserBriefDraft {
	return {
		intent: '',
		audience: '',
		prior_knowledge: '',
		extra_context: '',
		mode: 'balanced',
		signals: {
			topic_type: null,
			learning_outcome: null,
			class_style: [],
			format: null
		},
		preferences: {
			tone: 'supportive',
			reading_level: 'standard',
			explanation_style: 'balanced',
			example_style: 'everyday',
			brevity: 'balanced'
		},
		constraints: {
			more_practice: false,
			keep_short: false,
			use_visuals: false,
			print_first: false
		}
	};
}

function formatDefaultAudience(profile: TeacherProfile): string {
	if (profile.default_audience_description.trim()) {
		return profile.default_audience_description.trim();
	}

	const labels: Record<TeacherProfile['default_grade_band'], string> = {
		primary: 'Primary class',
		middle: 'Middle school class',
		high_school: 'High school class',
		undergraduate: 'Undergraduate cohort',
		adult: 'Adult learners'
	};

	return labels[profile.default_grade_band];
}

export function applyTeacherProfileDefaults(profile: TeacherProfile): void {
	const defaults = emptyDraft();
	briefDraft.update((draft) => ({
		...draft,
		audience: draft.audience.trim() ? draft.audience : formatDefaultAudience(profile),
		extra_context: draft.extra_context.trim()
			? draft.extra_context
			: profile.classroom_context.trim(),
		preferences: {
			tone:
				draft.preferences.tone !== defaults.preferences.tone
					? draft.preferences.tone
					: profile.delivery_preferences.tone,
			reading_level:
				draft.preferences.reading_level !== defaults.preferences.reading_level
					? draft.preferences.reading_level
					: profile.delivery_preferences.reading_level,
			explanation_style:
				draft.preferences.explanation_style !== defaults.preferences.explanation_style
					? draft.preferences.explanation_style
					: profile.delivery_preferences.explanation_style,
			example_style:
				draft.preferences.example_style !== defaults.preferences.example_style
					? draft.preferences.example_style
					: profile.delivery_preferences.example_style,
			brevity:
				draft.preferences.brevity !== defaults.preferences.brevity
					? draft.preferences.brevity
					: profile.delivery_preferences.brevity
		},
		constraints: {
			more_practice:
				draft.constraints.more_practice !== defaults.constraints.more_practice
					? draft.constraints.more_practice
					: profile.delivery_preferences.more_practice,
			keep_short:
				draft.constraints.keep_short !== defaults.constraints.keep_short
					? draft.constraints.keep_short
					: profile.delivery_preferences.keep_short,
			use_visuals:
				draft.constraints.use_visuals !== defaults.constraints.use_visuals
					? draft.constraints.use_visuals
					: profile.delivery_preferences.use_visuals,
			print_first:
				draft.constraints.print_first !== defaults.constraints.print_first
					? draft.constraints.print_first
					: profile.delivery_preferences.print_first
		}
	}));
}

export function emptyPlanDraft(): PlanDraft {
	return {
		template_decision: null,
		lesson_rationale: '',
		warning: null,
		sections: [],
		is_complete: false,
		error: null
	};
}

export const studioState = writable<StudioState>('idle');
export const briefDraft = writable<UserBriefDraft>(emptyDraft());
export const planDraft = writable<PlanDraft>(emptyPlanDraft());
export const editedSpec = writable<PlanningGenerationSpec | null>(null);
export const planningMs = writable<number>(0);
export const contracts = writable<StudioTemplateContract[]>([]);
export const generationState = writable<StudioGenerationState>({
	accepted: null,
	document: null,
	connectionBanner: null
});

export function resetPlanState(): void {
	planDraft.set(emptyPlanDraft());
	editedSpec.set(null);
	planningMs.set(0);
	generationState.set({
		accepted: null,
		document: null,
		connectionBanner: null
	});
}

export function returnToIdle(): void {
	resetPlanState();
	studioState.set('idle');
}

export function beginPlanning(): void {
	planDraft.set(emptyPlanDraft());
	editedSpec.set(null);
	planningMs.set(0);
	studioState.set('planning');
}

export function setTemplateDecision(
	templateDecision: PlanDraft['template_decision'],
	lessonRationale: string,
	warning: string | null
): void {
	planDraft.update((draft) => ({
		...draft,
		template_decision: templateDecision,
		lesson_rationale: lessonRationale,
		warning
	}));
}

export function appendPlannedSection(section: PlanningSectionPlan): void {
	planDraft.update((draft) => ({
		...draft,
		sections: [...draft.sections, section]
	}));
}

export function completePlanning(spec: PlanningGenerationSpec, elapsedMs: number): void {
	planDraft.update((draft) => ({
		...draft,
		is_complete: true,
		error: null,
		warning: spec.warning,
		lesson_rationale: spec.lesson_rationale
	}));
	// Override status to 'reviewed' — the teacher has now seen and can edit the plan
	editedSpec.set({
		...spec,
		status: 'reviewed'
	});
	planningMs.set(elapsedMs);
	studioState.set('reviewing');
}

export function failPlanning(message: string): void {
	planDraft.update((draft) => ({
		...draft,
		error: message
	}));
}

export function updateSection(
	sectionId: string,
	updater: (section: PlanningSectionPlan) => PlanningSectionPlan
): void {
	const current = get(editedSpec);
	if (!current) return;
	editedSpec.set({
		...current,
		sections: current.sections.map((section) =>
			section.id === sectionId ? updater(section) : section
		)
	});
}

export function updateTemplateSelection(
	contract: StudioTemplateContract,
	sections: PlanningSectionPlan[]
): void {
	const current = get(editedSpec);
	if (!current) return;
	editedSpec.set({
		...current,
		template_id: contract.id,
		template_decision: {
			...current.template_decision,
			chosen_id: contract.id,
			chosen_name: contract.name,
			rationale: `Teacher selected ${contract.name} for this lesson.`
		},
		committed_budgets: contract.component_budget,
		sections
	});
}

export function setContracts(nextContracts: StudioTemplateContract[]): void {
	contracts.set(nextContracts);
}

export function setGenerationAccepted(accepted: StudioGenerationState['accepted']): void {
	generationState.update((state) => ({
		...state,
		accepted
	}));
}

export function setGenerationDocument(document: StudioGenerationState['document']): void {
	generationState.update((state) => ({
		...state,
		document
	}));
}

export function setGenerationBanner(message: string | null): void {
	generationState.update((state) => ({
		...state,
		connectionBanner: message
	}));
}
