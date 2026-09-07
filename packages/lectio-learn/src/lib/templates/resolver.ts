import { DEV } from 'esm-env';

import { basePresetMap } from '$lib/presets/base-presets';
import { getTemplateById } from '$lib/templates/registry';
import type { TemplateDefinition, TemplatePresetDefinition } from '$lib/templates/types';

export const DEFAULT_PRESET_ID = 'warm-paper';

export function resolveTemplateDefinition(templateId: string) {
	return getTemplateById(templateId);
}

export function resolveTemplatePreset(
	definition: TemplateDefinition,
	presetId: string = DEFAULT_PRESET_ID
): TemplatePresetDefinition | null {
	const allowedPresets = definition.presets;
	const resolvedPreset =
		allowedPresets.find((preset) => preset.id === presetId) ??
		allowedPresets.find((preset) => preset.id === DEFAULT_PRESET_ID) ??
		allowedPresets[0] ??
		basePresetMap[DEFAULT_PRESET_ID] ??
		null;

	if (DEV && (!basePresetMap[presetId] || !allowedPresets.some((preset) => preset.id === presetId))) {
		console.warn(
			`[Lectio] Unknown or unsupported preset "${presetId}" for template "${definition.contract.id}". Falling back to "${resolvedPreset?.id ?? DEFAULT_PRESET_ID}".`
		);
	}

	return resolvedPreset;
}
