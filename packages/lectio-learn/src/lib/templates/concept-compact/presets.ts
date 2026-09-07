import { basePresets } from '$lib/presets/base-presets';

export const conceptCompactPresetIds = [
	'blue-classroom',
	'warm-paper',
	'minimal-light'
] as const;

export const conceptCompactPresets = basePresets.filter((preset) =>
	conceptCompactPresetIds.includes(
		preset.id as (typeof conceptCompactPresetIds)[number]
	)
);
