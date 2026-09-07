import { basePresets } from '$lib/presets/base-presets';

export const interactiveLabPresetIds = [
	'blue-classroom',
	'warm-paper',
	'calm-green',
	'high-contrast-focus'
] as const;

export const interactiveLabPresets = basePresets.filter((preset) =>
	interactiveLabPresetIds.includes(preset.id as (typeof interactiveLabPresetIds)[number])
);
