import type { Component } from "svelte";

import type { BehaviourMode, SectionContent } from "$lib/schema/types";

export type TemplateFamily =
  | "guided-concept"
  | "visual-exploration"
  | "compare-distinguish"
  | "narrative-timeline"
  | "process-procedure"
  | "focus-accommodation";

export type LessonIntent =
  | "introduce-concept"
  | "explain-visually"
  | "compare-ideas"
  | "teach-sequence"
  | "teach-procedure"
  | "reduce-overload"
  | "reinforce-learning"
  | "build-rigor";

export type LearnerFit =
  | "general"
  | "visual"
  | "analytical"
  | "narrative"
  | "adhd-friendly"
  | "dyslexia-sensitive"
  | "scaffolded"
  | "advanced";

export type InteractionLevel = "none" | "light" | "medium" | "high";

export type ReadingStyle =
  | "linear-guided"
  | "visual-first"
  | "side-by-side"
  | "chronological"
  | "chunked-focus"
  | "formal-rigorous"
  | "process-led";

export interface TemplateGenerationGuidance {
  tone: string;
  pacing: string;
  chunking: string;
  emphasis: string;
  avoid: string[];
}

export type SectionRole =
  | 'intro'
  | 'explain'
  | 'practice'
  | 'summary'
  | 'process'
  | 'compare'
  | 'timeline'
  | 'visual'
  | 'discover';

export interface TemplateContract {
  // ── Identity ──────────────────────────────────────────────────────────────
  id: string;
  name: string;
  family: TemplateFamily;
  intent: LessonIntent;
  tagline: string;
  readingStyle: ReadingStyle;
  tags: string[];

  // ── Audience and fit ──────────────────────────────────────────────────────
  bestFor: string[];
  notIdealFor: string[];
  learnerFit: LearnerFit[];
  subjects: string[];
  interactionLevel: InteractionLevel;

  // ── Component contract ─────────────────────────────────────────────────────
  always_present: string[];
  contextually_present?: string[];
  available_components: string[];
  component_budget: Partial<Record<string, number>>;
  max_per_section: Partial<Record<string, number>>;
  defaultBehaviours: Partial<Record<string, BehaviourMode>>;

  // ── Section role defaults ──────────────────────────────────────────────────
  section_role_defaults: Partial<Record<SectionRole, string[]>>;

  // ── Signal affinity ────────────────────────────────────────────────────────
  signal_affinity: {
    topic_type: Partial<Record<'concept' | 'process' | 'facts' | 'mixed', number>>;
    learning_outcome: Partial<Record<'understand-why' | 'be-able-to-do' | 'remember-terms' | 'apply-to-new', number>>;
    class_style: Partial<Record<'tries-before-told' | 'needs-explanation-first' | 'engages-with-visuals' | 'responds-to-worked-examples' | 'restless-without-activity', number>>;
    format: Partial<Record<'printed-booklet' | 'screen-based' | 'both', number>>;
  };

  // ── Layout and print ───────────────────────────────────────────────────────
  layoutNotes: string[];
  responsiveRules: string[];
  printRules: string[];

  // ── Meta ────────────────────────────────────────────────────────────────────
  allowedPresets: string[];
  whyThisTemplateExists: string;
  generationGuidance: TemplateGenerationGuidance;
  preview: {
    subjectExample: string;
    sectionTitle: string;
    previewContentId: string;
  };
}

export interface TemplatePreview {
  section: SectionContent;
  summary: string;
}

export interface TemplatePresetGuardrails {
  headingScale: { min: number; max: number };
  bodyScale: { min: number; max: number };
  spacingScale: { min: number; max: number };
}

export interface TemplatePresetDefinition {
  id: string;
  name: string;
  description: string;
  palette: string;
  typography: string;
  density: string;
  surfaceStyle: string;
  guardrails: TemplatePresetGuardrails;
}

export interface TemplateDefinition {
  contract: TemplateContract;
  preview: TemplatePreview;
  presets: TemplatePresetDefinition[];
  render: Component<{ section: SectionContent }>;
  readmePath: string;
}

export interface TemplateFilters {
  family?: TemplateFamily;
  intent?: LessonIntent;
  learnerFit?: LearnerFit;
  subject?: string;
  interactionLevel?: InteractionLevel;
}

export interface TemplateValidationResult {
  errors: string[];
  warnings: string[];
}
