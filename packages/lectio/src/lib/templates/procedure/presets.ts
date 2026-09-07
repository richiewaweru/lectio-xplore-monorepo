import { basePresets } from '$lib/presets/base-presets';

export const procedurePresetIds = [
	'blue-classroom',
	'warm-paper',
	'minimal-light'
] as const;

export const procedurePresets = basePresets.filter((preset) =>
	procedurePresetIds.includes(preset.id as (typeof procedurePresetIds)[number])
);
