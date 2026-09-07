import { basePresets } from '$lib/presets/base-presets';

export const visualLedPresetIds = [
	'calm-green',
	'blue-classroom',
	'high-contrast-focus'
] as const;

export const visualLedPresets = basePresets.filter((preset) =>
	visualLedPresetIds.includes(preset.id as (typeof visualLedPresetIds)[number])
);
