import type { TemplatePresetDefinition } from "$lib/templates/types";

const sharedGuardrails = {
  headingScale: { min: 0.95, max: 1.1 },
  bodyScale: { min: 0.95, max: 1.08 },
  spacingScale: { min: 0.95, max: 1.15 }
} as const;

export const basePresets: TemplatePresetDefinition[] = [
  {
    id: "blue-classroom",
    name: "Blue Classroom",
    description: "Professional classroom blue with strong structure for screen-first lessons.",
    palette: "navy, sky, parchment",
    typography: "standard",
    density: "standard",
    surfaceStyle: "crisp",
    guardrails: sharedGuardrails
  },
  {
    id: "warm-paper",
    name: "Warm Paper",
    description: "Editorial, warm neutral surfaces that feel close to a printed workbook.",
    palette: "sand, amber, ink",
    typography: "standard",
    density: "comfortable",
    surfaceStyle: "soft",
    guardrails: sharedGuardrails
  },
  {
    id: "calm-green",
    name: "Calm Green",
    description: "Lower-stimulation greens tuned for long-form reading and support flows.",
    palette: "sage, pine, cream",
    typography: "reading-support",
    density: "comfortable",
    surfaceStyle: "soft",
    guardrails: sharedGuardrails
  },
  {
    id: "high-contrast-focus",
    name: "High Contrast Focus",
    description: "Sharper contrast and focus cues for accessibility-sensitive reading.",
    palette: "ink, ivory, signal amber",
    typography: "reading-support",
    density: "standard",
    surfaceStyle: "minimal",
    guardrails: sharedGuardrails
  },
  {
    id: "minimal-light",
    name: "Minimal Light",
    description: "Quiet, print-friendly white surfaces with minimal decoration.",
    palette: "white, slate, graphite",
    typography: "standard",
    density: "comfortable",
    surfaceStyle: "minimal",
    guardrails: sharedGuardrails
  }
];

export const basePresetMap = Object.fromEntries(
  basePresets.map((preset) => [preset.id, preset])
) satisfies Record<string, TemplatePresetDefinition>;
