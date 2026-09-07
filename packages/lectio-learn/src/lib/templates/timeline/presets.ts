import { basePresets } from '$lib/presets/base-presets';

export const timelinePresetIds = [
	'warm-paper',
	'blue-classroom',
	'minimal-light'
] as const;

export const timelinePresets = basePresets.filter((preset) =>
	timelinePresetIds.includes(preset.id as (typeof timelinePresetIds)[number])
);
