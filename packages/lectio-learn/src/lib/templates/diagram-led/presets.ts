import { basePresets } from '$lib/presets/base-presets';

export const diagramLedPresetIds = [
	'calm-green',
	'blue-classroom',
	'warm-paper'
] as const;

export const diagramLedPresets = basePresets.filter((preset) =>
	diagramLedPresetIds.includes(preset.id as (typeof diagramLedPresetIds)[number])
);
