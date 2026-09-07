// Template validation — runs at registry load time.
// Catches broken templates before they reach the gallery.
//
// Three checks per template:
//   validateTemplateContract  — structure, references, presets
//   validateTemplatePreview   — preview section has required content
//   validateTemplateDefinition — both combined (the one you call)

import { basePresetMap } from '$lib/presets/base-presets';
import { getComponentById, getComponentFieldMap } from '$lib/schema/registry';
import type {
	TemplateContract,
	TemplateDefinition,
	TemplateValidationResult
} from '$lib/templates/types';
import type { SectionContent } from '$lib/schema/types';

// Derived from the registry — never hardcoded here.
// When you add a new component with sectionField declared,
// it is automatically included. This file never needs to change.
const componentFieldMap = getComponentFieldMap();

function hasPreviewField(section: SectionContent, componentId: string): boolean {
	const field = componentFieldMap[componentId];
	if (!field) return false;
	return Boolean(section[field]);
}

export function validateTemplateContract(contract: TemplateContract): TemplateValidationResult {
	const errors: string[] = [];
	const warnings: string[] = [];

	// ── Required prose fields ─────────────────────────────
	if (!contract.tagline.trim()) {
		errors.push(`${contract.id}: tagline is required.`);
	}

	if (!contract.bestFor.length || !contract.notIdealFor.length) {
		errors.push(`${contract.id}: bestFor and notIdealFor are required.`);
	}

	if (
		!contract.always_present.length &&
		contract.id !== 'guided-concept-path' &&
		contract.id !== 'open-canvas'
	) {
		errors.push(`${contract.id}: always_present must not be empty.`);
	}

	// ── All component ids must exist in the registry ──────
	const allComponentIds = [...contract.always_present, ...contract.available_components];

	for (const componentId of allComponentIds) {
		if (!getComponentById(componentId)) {
			errors.push(`${contract.id}: unknown component "${componentId}".`);
		}
	}

	// ── Budget keys must reference valid components ───────
	for (const componentId of Object.keys(contract.component_budget)) {
		if (!getComponentById(componentId)) {
			errors.push(`${contract.id}: component_budget references unknown component "${componentId}".`);
		}
	}

	for (const componentId of Object.keys(contract.max_per_section)) {
		if (!getComponentById(componentId)) {
			errors.push(`${contract.id}: max_per_section references unknown component "${componentId}".`);
		}
	}

	// ── defaultBehaviours must reference valid components
	// and behaviours those components actually support ─────
	for (const [componentId, behaviour] of Object.entries(contract.defaultBehaviours)) {
		const meta = getComponentById(componentId);

		if (!meta) {
			errors.push(
				`${contract.id}: behaviour set for unknown component "${componentId}".`
			);
			continue;
		}

		if (behaviour && !meta.behaviourModes.includes(behaviour)) {
			errors.push(
				`${contract.id}: behaviour "${behaviour}" is not supported by "${componentId}". ` +
				`Supported: ${meta.behaviourModes.join(', ')}.`
			);
		}
	}

	// ── All allowed presets must exist in the preset registry
	for (const presetId of contract.allowedPresets) {
		if (!basePresetMap[presetId]) {
			errors.push(`${contract.id}: unknown preset "${presetId}".`);
		}
	}

	// ── Consistency warnings ──────────────────────────────
	if (contract.interactionLevel === 'none' && Object.keys(contract.defaultBehaviours).length) {
		warnings.push(
			`${contract.id}: interactionLevel is "none" but defaultBehaviours is not empty.`
		);
	}

	return { errors, warnings };
}

export function validateTemplatePreview(
	definition: TemplateDefinition
): TemplateValidationResult {
	const errors: string[] = [];
	const warnings: string[] = [];

	// Every always_present component must have corresponding content
	// in the preview section, so the gallery card renders correctly.
	for (const componentId of definition.contract.always_present) {
		if (!hasPreviewField(definition.preview.section, componentId)) {
			errors.push(
				`${definition.contract.id}: preview is missing content for ` +
				`always_present component "${componentId}".`
			);
		}
	}

	return { errors, warnings };
}

export function validateTemplateDefinition(
	definition: TemplateDefinition
): TemplateValidationResult {
	const contractResult = validateTemplateContract(definition.contract);
	const previewResult = validateTemplatePreview(definition);

	return {
		errors: [...contractResult.errors, ...previewResult.errors],
		warnings: [...contractResult.warnings, ...previewResult.warnings]
	};
}
