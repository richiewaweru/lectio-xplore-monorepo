import { lectioComponentModules } from '$lib/lectio/registry/components';
import { LECTIO_PHASES } from '$lib/lectio/core/phases';
import {
	CONTENT_CONTRACT_EXCLUDED_COMPONENT_IDS,
	CONTENT_CONTRACT_TEMPLATE_IDS,
	isContentContractEligible
} from '$lib/lectio/export-policy';
import type { LectioContentModule } from '$lib/lectio/core/types';
import { LECTIO_PRINT_SURFACE } from '$lib/lectio/core/print-surface';
import { guidedConceptPathContract } from '$lib/templates/guided-concept-path/config';
import { openCanvasContract } from '$lib/templates/open-canvas/config';

type JsonObject = Record<string, unknown>;

const EXCLUDED_COMPONENT_REASON: Record<string, string> = {
	'image-block': 'Editor-attached image content, not a generation-facing section block.',
	'video-embed': 'Editor-attached video content, not a generation-facing section block.',
	'glossary-inline': 'Inline helper content, not a standalone section block.'
};

const templates = [guidedConceptPathContract, openCanvasContract].filter((template) =>
	CONTENT_CONTRACT_TEMPLATE_IDS.includes(template.id as (typeof CONTENT_CONTRACT_TEMPLATE_IDS)[number])
);

function toComponentCard(module: LectioContentModule, sectionProps: JsonObject): JsonObject {
	const sectionField = String(module.metadata.sectionField);
	return {
		component_id: module.metadata.id,
		section_field: module.metadata.sectionField,
		role: module.metadata.role,
		cognitive_job: module.metadata.cognitiveJob,
		subjects: module.metadata.subjects,
		capacity: module.metadata.capacity,
		capabilities: module.metadata.capabilities,
		writer_excluded: module.metadata.capabilities.isMedia,
		status: module.metadata.status,
		schema_summary: sectionProps[sectionField] ?? null,
		field_contracts: module.contentContract?.fieldContracts ?? {},
		component_constraints: module.contentContract?.componentConstraints ?? [],
		examples: module.examples,
		/** Canonical print spec (same object as `print_behavior` for backward compatibility) */
		print: module.print,
		print_behavior: module.print
	};
}

function buildPlannerIndex(modules: readonly LectioContentModule[]): JsonObject {
	const exportableModules = modules.filter((module) => module.metadata.status !== 'planned');
	const phaseMap: Record<string, { name: string; description: string; components: string[] }> = {};

	for (const [phaseNumStr, phaseDef] of Object.entries(LECTIO_PHASES)) {
		const phaseNum = Number(phaseNumStr);
		const componentIds = exportableModules
			.filter((module) => module.metadata.phase === phaseNum)
			.map((module) => module.metadata.id);

		if (componentIds.length === 0) continue;

		phaseMap[phaseNumStr] = {
			name: phaseDef.name,
			description: phaseDef.description,
			components: componentIds
		};
	}

	return {
		component_ids: exportableModules.map((module) => module.metadata.id),
		phase_map: phaseMap
	};
}

export function buildLectioContentContract(
	sectionProps: JsonObject,
	version = '1.0.0'
): JsonObject {
	const included: LectioContentModule[] = lectioComponentModules.filter((module) =>
		isContentContractEligible(module)
	);
	for (const module of included) {
		if (!module.contentContract) {
			console.warn(
				`[Lectio] No content-contract.ts for mapped component "${module.metadata.id}". ` +
					'field_contracts will be empty in the exported card. ' +
					'Add a content-contract.ts to this component folder.'
			);
		}
	}
	const cards = included.map((module) => toComponentCard(module, sectionProps));

	return {
		version,
		source: 'lectio',
		print_surface: LECTIO_PRINT_SURFACE,
		default_template_id: 'guided-concept-path',
		formatting_policy: {
			default: 'plain_text unless field contract says otherwise',
			inline_markdown: 'Supports bold, italic, inline code, and inline math using $...$.',
			block_markdown:
				'Supports paragraphs, lists, bold, italic, and math using $...$ or $$...$$.',
			latex_raw: 'Raw LaTeX only. Do not wrap in $...$ unless field contract says markdown math.',
			plain_phrase_list:
				'Plain phrases, no markdown. Usually used for matching and highlighting.',
			positioned_callouts: 'Labels positioned using x/y percentages from 0 to 100.'
		},
		templates: Object.fromEntries(
			templates.map((template) => [
				template.id,
				{
					id: template.id,
					name: template.name,
					always_present: template.always_present,
					contextually_present: template.contextually_present ?? [],
					available_components: template.available_components,
					component_budget: template.component_budget,
					max_per_section: template.max_per_section
				}
			])
		),
		planner_index: buildPlannerIndex(included),
		component_cards: Object.fromEntries(cards.map((card) => [String(card.component_id), card])),
		excluded_components: Object.fromEntries(
			CONTENT_CONTRACT_EXCLUDED_COMPONENT_IDS.map((componentId) => [
				componentId,
				{
					component_id: componentId,
					reason: EXCLUDED_COMPONENT_REASON[componentId] ?? 'Excluded from the generation-facing contract.'
				}
			])
		)
	};
}
