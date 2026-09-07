import type { TemplateDefinition, TemplateFilters } from '$lib/templates/types';
import { validateTemplateDefinition } from '$lib/templates/validation';

import { classificationContract } from '$lib/templates/classification/config';
import ClassificationLayout from '$lib/templates/classification/layout.svelte';
import { classificationPresets } from '$lib/templates/classification/presets';
import { classificationPreview } from '$lib/templates/classification/preview';
import { compareAndApplyContract } from '$lib/templates/compare-and-apply/config';
import CompareAndApplyLayout from '$lib/templates/compare-and-apply/layout.svelte';
import { compareAndApplyPresets } from '$lib/templates/compare-and-apply/presets';
import { compareAndApplyPreview } from '$lib/templates/compare-and-apply/preview';
import { conceptCompactContract } from '$lib/templates/concept-compact/config';
import ConceptCompactLayout from '$lib/templates/concept-compact/layout.svelte';
import { conceptCompactPresets } from '$lib/templates/concept-compact/presets';
import { conceptCompactPreview } from '$lib/templates/concept-compact/preview';
import { diagramLedContract } from '$lib/templates/diagram-led/config';
import DiagramLedLayout from '$lib/templates/diagram-led/layout.svelte';
import { diagramLedPresets } from '$lib/templates/diagram-led/presets';
import { diagramLedPreview } from '$lib/templates/diagram-led/preview';
import { formalTrackContract } from '$lib/templates/formal-track/config';
import FormalTrackLayout from '$lib/templates/formal-track/layout.svelte';
import { formalTrackPresets } from '$lib/templates/formal-track/presets';
import { formalTrackPreview } from '$lib/templates/formal-track/preview';
import { guidedConceptPathContract } from '$lib/templates/guided-concept-path/config';
import GuidedConceptPathLayout from '$lib/templates/guided-concept-path/layout.svelte';
import { guidedConceptPathPresets } from '$lib/templates/guided-concept-path/presets';
import { guidedConceptPathPreview } from '$lib/templates/guided-concept-path/preview';
import { guidedDiscoveryContract } from '$lib/templates/guided-discovery/config';
import GuidedDiscoveryLayout from '$lib/templates/guided-discovery/layout.svelte';
import { guidedDiscoveryPresets } from '$lib/templates/guided-discovery/presets';
import { guidedDiscoveryPreview } from '$lib/templates/guided-discovery/preview';
import { interactiveLabContract } from '$lib/templates/interactive-lab/config';
import InteractiveLabLayout from '$lib/templates/interactive-lab/layout.svelte';
import { interactiveLabPresets } from '$lib/templates/interactive-lab/presets';
import { interactiveLabPreview } from '$lib/templates/interactive-lab/preview';
import { lowLoadContract } from '$lib/templates/low-load/config';
import LowLoadLayout from '$lib/templates/low-load/layout.svelte';
import { lowLoadPresets } from '$lib/templates/low-load/presets';
import { lowLoadPreview } from '$lib/templates/low-load/preview';
import { procedureContract } from '$lib/templates/procedure/config';
import ProcedureLayout from '$lib/templates/procedure/layout.svelte';
import { procedurePresets } from '$lib/templates/procedure/presets';
import { procedurePreview } from '$lib/templates/procedure/preview';
import { timelineContract } from '$lib/templates/timeline/config';
import TimelineLayout from '$lib/templates/timeline/layout.svelte';
import { timelinePresets } from '$lib/templates/timeline/presets';
import { timelinePreview } from '$lib/templates/timeline/preview';
import { openCanvasContract } from '$lib/templates/open-canvas/config';
import OpenCanvasLayout from '$lib/templates/open-canvas/layout.svelte';
import { openCanvasPresets } from '$lib/templates/open-canvas/presets';
import { openCanvasPreview } from '$lib/templates/open-canvas/preview';
import { visualLedContract } from '$lib/templates/visual-led/config';
import VisualLedLayout from '$lib/templates/visual-led/layout.svelte';
import { visualLedPresets } from '$lib/templates/visual-led/presets';
import { visualLedPreview } from '$lib/templates/visual-led/preview';

export const templateRegistry: TemplateDefinition[] = [
	{
		contract: guidedConceptPathContract,
		preview: guidedConceptPathPreview,
		presets: guidedConceptPathPresets,
		render: GuidedConceptPathLayout,
		readmePath: 'src/lib/templates/guided-concept-path/README.md'
	},
	{
		contract: visualLedContract,
		preview: visualLedPreview,
		presets: visualLedPresets,
		render: VisualLedLayout,
		readmePath: 'src/lib/templates/visual-led/README.md'
	},
	{
		contract: compareAndApplyContract,
		preview: compareAndApplyPreview,
		presets: compareAndApplyPresets,
		render: CompareAndApplyLayout,
		readmePath: 'src/lib/templates/compare-and-apply/README.md'
	},
	{
		contract: lowLoadContract,
		preview: lowLoadPreview,
		presets: lowLoadPresets,
		render: LowLoadLayout,
		readmePath: 'src/lib/templates/low-load/README.md'
	},
	{
		contract: conceptCompactContract,
		preview: conceptCompactPreview,
		presets: conceptCompactPresets,
		render: ConceptCompactLayout,
		readmePath: 'src/lib/templates/concept-compact/README.md'
	},
	{
		contract: formalTrackContract,
		preview: formalTrackPreview,
		presets: formalTrackPresets,
		render: FormalTrackLayout,
		readmePath: 'src/lib/templates/formal-track/README.md'
	},
	{
		contract: diagramLedContract,
		preview: diagramLedPreview,
		presets: diagramLedPresets,
		render: DiagramLedLayout,
		readmePath: 'src/lib/templates/diagram-led/README.md'
	},
	{
		contract: classificationContract,
		preview: classificationPreview,
		presets: classificationPresets,
		render: ClassificationLayout,
		readmePath: 'src/lib/templates/classification/README.md'
	},
	{
		contract: timelineContract,
		preview: timelinePreview,
		presets: timelinePresets,
		render: TimelineLayout,
		readmePath: 'src/lib/templates/timeline/README.md'
	},
	{
		contract: procedureContract,
		preview: procedurePreview,
		presets: procedurePresets,
		render: ProcedureLayout,
		readmePath: 'src/lib/templates/procedure/README.md'
	},
	{
		contract: interactiveLabContract,
		preview: interactiveLabPreview,
		presets: interactiveLabPresets,
		render: InteractiveLabLayout,
		readmePath: 'src/lib/templates/interactive-lab/README.md'
	},
	{
		contract: guidedDiscoveryContract,
		preview: guidedDiscoveryPreview,
		presets: guidedDiscoveryPresets,
		render: GuidedDiscoveryLayout,
		readmePath: 'src/lib/templates/guided-discovery/README.md'
	},
	{
		contract: openCanvasContract,
		preview: openCanvasPreview,
		presets: openCanvasPresets,
		render: OpenCanvasLayout,
		readmePath: 'src/lib/templates/open-canvas/README.md'
	}
];

export const templateRegistryMap = Object.fromEntries(
	templateRegistry.map((definition) => [definition.contract.id, definition])
) satisfies Record<string, TemplateDefinition>;

export function getTemplateById(templateId: string) {
	return templateRegistryMap[templateId];
}

export function filterTemplates(filters: TemplateFilters) {
	return templateRegistry.filter((definition) => {
		const { contract } = definition;

		if (filters.family && contract.family !== filters.family) {
			return false;
		}

		if (filters.intent && contract.intent !== filters.intent) {
			return false;
		}

		if (filters.learnerFit && !contract.learnerFit.includes(filters.learnerFit)) {
			return false;
		}

		if (
			filters.subject &&
			!contract.subjects.some((subject) => subject.toLowerCase() === filters.subject?.toLowerCase())
		) {
			return false;
		}

		if (filters.interactionLevel && contract.interactionLevel !== filters.interactionLevel) {
			return false;
		}

		return true;
	});
}

export function getTemplateFamilies() {
	return Array.from(new Set(templateRegistry.map((definition) => definition.contract.family)));
}

export function validateAllTemplates() {
	return templateRegistry.map((definition) => ({
		id: definition.contract.id,
		...validateTemplateDefinition(definition)
	}));
}
