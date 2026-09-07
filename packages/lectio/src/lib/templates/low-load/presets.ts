import { basePresets } from '$lib/presets/base-presets';

export const lowLoadPresetIds = [
	'high-contrast-focus',
	'calm-green',
	'warm-paper',
	'minimal-light'
] as const;

export const lowLoadPresets = basePresets.filter((preset) =>
	lowLoadPresetIds.includes(preset.id as (typeof lowLoadPresetIds)[number])
);
