import { basePresets } from '$lib/presets/base-presets';

export const guidedDiscoveryPresetIds = [
	'blue-classroom',
	'warm-paper',
	'calm-green',
	'minimal-light'
] as const;

export const guidedDiscoveryPresets = basePresets.filter((preset) =>
	guidedDiscoveryPresetIds.includes(preset.id as (typeof guidedDiscoveryPresetIds)[number])
);
