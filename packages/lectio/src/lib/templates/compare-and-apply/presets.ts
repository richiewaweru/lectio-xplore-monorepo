import { basePresets } from '$lib/presets/base-presets';

export const compareAndApplyPresetIds = [
	'blue-classroom',
	'warm-paper',
	'high-contrast-focus'
] as const;

export const compareAndApplyPresets = basePresets.filter((preset) =>
	compareAndApplyPresetIds.includes(preset.id as (typeof compareAndApplyPresetIds)[number])
);
