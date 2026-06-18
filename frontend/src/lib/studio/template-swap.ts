import type {
	PlanningGenerationSpec,
	PlanningSectionPlan,
	SectionRole,
	StudioTemplateContract,
	TemplateAlternative
} from '$lib/types';

const VISUAL_COMPONENTS = new Set([
	'diagram-block',
	'diagram-series',
	'diagram-compare',
	'simulation-block'
]);

function componentsForRole(
	contract: StudioTemplateContract,
	role: SectionRole
): PlanningSectionPlan['selected_components'] {
	const direct = contract.section_role_defaults[role];
	if (direct?.length) {
		return [...direct];
	}

	if (role === 'summary') {
		return contract.always_present.filter((component) =>
			['what-next-bridge', 'summary-block'].includes(component)
		);
	}

	if (
		(role === 'discover' || role === 'visual') &&
		contract.section_role_defaults.explain?.length
	) {
		return [...contract.section_role_defaults.explain];
	}

	return [];
}

function supportsVisuals(contract: StudioTemplateContract): boolean {
	return contract.available_components.some((component) => VISUAL_COMPONENTS.has(component));
}

function buildAlternatives(
	spec: PlanningGenerationSpec,
	contract: StudioTemplateContract
): TemplateAlternative[] {
	const alternatives = spec.template_decision.alternatives.filter(
		(alternative) => alternative.template_id !== contract.id
	);

	if (spec.template_decision.chosen_id !== contract.id) {
		alternatives.unshift({
			template_id: spec.template_decision.chosen_id,
			template_name: spec.template_decision.chosen_name,
			fit_score: spec.template_decision.fit_score,
			why_not_chosen: 'Teacher preferred a different template during review.'
		});
	}

	return alternatives.slice(0, 3);
}

export interface AuthoredSection {
	order: number;
	title: string | null;
	focus_note: string | null;
	transition_note?: string | null;
}

export function mergeAuthoredSections(
	newSpec: PlanningGenerationSpec,
	authored: AuthoredSection[]
): PlanningGenerationSpec {
	const authoredByOrder = new Map(authored.map((a) => [a.order, a]));

	return {
		...newSpec,
		sections: newSpec.sections.map((section) => {
			const edit = authoredByOrder.get(section.order);
			if (!edit) return section;
			return {
				...section,
				title: edit.title ?? section.title,
				focus_note: edit.focus_note ?? section.focus_note,
				transition_note: edit.transition_note ?? section.transition_note
			};
		})
	};
}

export function swapTemplateInSpec(
	spec: PlanningGenerationSpec,
	contract: StudioTemplateContract
): PlanningGenerationSpec {
	const visualsSupported = supportsVisuals(contract);

	return {
		...spec,
		template_id: contract.id,
		template_decision: {
			...spec.template_decision,
			chosen_id: contract.id,
			chosen_name: contract.name,
			rationale: `Teacher selected ${contract.name} during review.`,
			alternatives: buildAlternatives(spec, contract)
		},
		committed_budgets: contract.component_budget,
		sections: spec.sections.map((section) => ({
			...section,
			selected_components: componentsForRole(contract, section.role),
			visual_policy: visualsSupported ? section.visual_policy : null,
			visual_placements: []
		}))
	};
}

export { componentsForRole };
