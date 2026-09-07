import { basePresets } from '$lib/presets/base-presets';

export const formalTrackPresetIds = ['warm-paper', 'minimal-light'] as const;

export const formalTrackPresets = basePresets.filter((preset) =>
	formalTrackPresetIds.includes(preset.id as (typeof formalTrackPresetIds)[number])
);
