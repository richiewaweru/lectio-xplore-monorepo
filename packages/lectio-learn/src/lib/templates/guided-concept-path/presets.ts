import { basePresets } from '$lib/presets/base-presets';

export const guidedConceptPathPresetIds = [
	'blue-classroom',
	'warm-paper',
	'calm-green',
	'high-contrast-focus'
] as const;

export const guidedConceptPathPresets = basePresets.filter((preset) =>
	guidedConceptPathPresetIds.includes(preset.id as (typeof guidedConceptPathPresetIds)[number])
);
