import { basePresets } from '$lib/presets/base-presets';

export const classificationPresetIds = [
	'blue-classroom',
	'warm-paper',
	'high-contrast-focus'
] as const;

export const classificationPresets = basePresets.filter((preset) =>
	classificationPresetIds.includes(preset.id as (typeof classificationPresetIds)[number])
);
