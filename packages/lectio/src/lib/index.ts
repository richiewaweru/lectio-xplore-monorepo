// ── Components ──────────────────────────────────────
export {
	SectionHeader,
	HookHero,
	ExplanationBlock,
	PrerequisiteStrip,
	WhatNextBridge,
	InterviewAnchor,
	CalloutBlock,
	SummaryBlock,
	SectionDivider,
	DefinitionCard,
	DefinitionFamily,
	RichText,
	GlossaryRail,
	GlossaryInline,
	InsightStrip,
	KeyFact,
	ComparisonGrid,
	WorkedExampleCard,
	ProcessSteps,
	PracticeStack,
	QuizCheck,
	AnswerKey,
	ReflectionPrompt,
	StudentTextbox,
	ShortAnswerQuestion,
	FillInTheBlank,
	PitfallAlert,
	DiagramBlock,
	DiagramCompare,
	DiagramSeries,
	VideoEmbed,
	ImageBlock,
	TimelineBlock,
	SimulationBlock
} from './components/lectio';

// ── Types ───────────────────────────────────────────
export type {
	SectionContent,
	SectionHeaderContent,
	HookHeroContent,
	ExplanationContent,
	ExplanationCallout,
	DefinitionContent,
	DefinitionFamilyContent,
	GlossaryContent,
	GlossaryTerm,
	GlossaryInlineProps,
	PracticeContent,
	PracticeProblem,
	PracticeHint,
	PracticeSolution,
	WorkedExampleContent,
	WorkedStep,
	PitfallContent,
	DiagramContent,
	DiagramCompareContent,
	DiagramSeriesContent,
	DiagramCallout,
	ComparisonGridContent,
	ComparisonColumn,
	ComparisonRow,
	TimelineContent,
	TimelineEvent,
	QuizContent,
	QuizOption,
	AnswerKeyContent,
	AnswerKeyEntry,
	AnswerKeyDiagnostic,
	ReflectionContent,
	InsightStripContent,
	InsightCell,
	ProcessContent,
	ProcessStepItem,
	PrerequisiteContent,
	PrerequisiteItem,
	InterviewContent,
	SimulationContent,
	InteractionSpec,
	InteractionContext,
	InteractionDimensions,
	DiagramSeriesStep,
	WhatNextContent,
	LevelPill,
	HookImage,
	HookType,
	ReflectionType,
	SimulationType,
	BehaviourMode,
	Difficulty,
	GradeBand,
	HintLevel,
	CalloutVariant,
	CalloutBlockContent,
	SummaryItem,
	SummaryBlockContent,
	SectionDividerContent,
	KeyFactContent,
	StudentTextboxContent,
	ShortAnswerContent,
	FillInBlankSegment,
	FillInBlankContent,
	VideoEmbedContent,
	ImageBlockContent
} from './schema/types';

// ── Registry ────────────────────────────────────────
export {
	componentRegistry,
	getStableComponents,
	getComponentsByGroup,
	getComponentsByIntent,
	getComponentsForSubject,
	getComponentById,
	getComponentFieldMap,
	PALETTE_GROUPS
} from './schema/registry';
export type { ComponentMeta, PaletteGroup, TeachingIntent } from './schema/registry';

// ── Validation ──────────────────────────────────────
export { validateSection, warnIfInvalid } from './schema/validate';

// ── Lesson document interchange + builder utilities ──
export type {
	LessonDocument,
	LessonDocumentVersion,
	BlockInstance,
	DocumentSection,
	MediaReference,
	DocumentValidationResult,
	FromSectionContentsMetadata,
	LearnerSectionIntent,
	SectionNavigationPolicy,
	SectionCompletionPolicy,
	SectionAssessmentMode,
	SectionConceptRef
} from './teacher/document';
export {
	fromSectionContents,
	toSectionContents,
	validateDocument,
	getFieldComponentMap,
	orderedDocumentSections,
	learnerSectionLabel,
	withDefaultLearnerSectionMeta,
	assertNoLearnerStateOnSection
} from './teacher/document';

export { getEmptyContent, getPreviewContent, assertFactoriesCoverRegistry } from './teacher/content-factories';

export { getEditSchema } from './teacher/edit-schemas';
export type { EditSchema, FieldSchema, FieldInputType } from './teacher/edit-schemas';

// ── Template system ─────────────────────────────────
export {
	templateRegistry,
	templateRegistryMap,
	getTemplateById,
	filterTemplates,
	getTemplateFamilies,
	validateAllTemplates
} from './templates/registry';
export { default as LectioThemeSurface } from './templates/LectioThemeSurface.svelte';
export { default as ResolvedTemplatePreviewSurface } from './templates/ResolvedTemplatePreviewSurface.svelte';
export { default as TemplateRuntimeSurface } from './templates/TemplateRuntimeSurface.svelte';
export { default as TemplatePreviewSurface } from './templates/TemplatePreviewSurface.svelte';
export { LectioBlockRuntimeSurface } from './runtime';
export type {
	TemplateContract,
	TemplateDefinition,
	TemplatePresetDefinition,
	TemplatePreview,
	TemplatePresetGuardrails,
	TemplateGenerationGuidance,
	TemplateFamily,
	LessonIntent,
	LearnerFit,
	InteractionLevel,
	ReadingStyle,
	SectionRole,
	TemplateFilters,
	TemplateValidationResult
} from './templates/types';
export {
	validateTemplateDefinition,
	validateTemplateContract,
	validateTemplatePreview
} from './templates/validation';

// ── Presets ─────────────────────────────────────────
export { basePresets, basePresetMap } from './presets/base-presets';

// ── Utility ─────────────────────────────────────────
export { cn } from './utils';

// ── Markdown utilities ───────────────────────────────
export { renderInlineMarkdown, renderBlockMarkdown, looksLikeLatex } from './utils/markdown';

// ── Web preview mode (not Page Print; Page uses @lectio/page) ──
// Kept for transitional Component Lectio screen/print-chrome routes.
export { providePrintMode, usePrintMode } from './utils/printContext';

// Web-native Learn metadata types (Phase 02)
export type {
	WebLearnHints,
	InteractionKind,
	ResponseEvaluation,
	NarrationRole,
	LearnerBand
} from './schema/component-meta';

// Learn interaction contracts (Phase 04)
export type {
	LearnInteractionContract,
	InteractionKindId,
	EvaluationResult,
	EvaluationOutcome,
	InteractionAttemptState,
	AttemptPolicy,
	FeedbackSpec,
	CompletionRule
} from './learn/interaction-contract';
export {
	evaluateInteraction,
	evaluateChoice,
	evaluateMultiSelect,
	evaluateFillBlank,
	evaluateNumeric,
	evaluateMatchPairs,
	evaluateSequence,
	validateInteractionContract,
	serializeInteractionContract,
	parseInteractionContract,
	quizContentToInteractionContract,
	fillBlankContentToInteractionContract,
	createAttemptState,
	recordAttempt,
	completeLessonInMemory,
	isComplete
} from './learn/interaction-contract';

// Learn interaction UI shells (Phase 04 closeout)
export { default as MultiSelectInteraction } from './learn/MultiSelectInteraction.svelte';
export { default as ChoiceInteraction } from './learn/ChoiceInteraction.svelte';
export { default as ImageChoiceInteraction } from './learn/ImageChoiceInteraction.svelte';
export { default as MatchPairsInteraction } from './learn/MatchPairsInteraction.svelte';
export { default as ClassifyInteraction } from './learn/ClassifyInteraction.svelte';
export { default as SequenceInteraction } from './learn/SequenceInteraction.svelte';
export { default as NumericInteraction } from './learn/NumericInteraction.svelte';
export { default as ShortResponseInteraction } from './learn/ShortResponseInteraction.svelte';
export { default as ImageHotspotInteraction } from './learn/ImageHotspotInteraction.svelte';
export { default as DragLabelInteraction } from './learn/DragLabelInteraction.svelte';
