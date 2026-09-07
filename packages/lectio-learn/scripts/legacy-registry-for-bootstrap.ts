// The component registry ΓÇö single source of truth.
// Drives the showcase, template generation, validation,
// and the pipeline contract export.
//
// ΓöÇΓöÇ HOW TO ADD A NEW COMPONENT ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
// 1. Create the .svelte file in src/lib/components/lectio/
// 2. Add an entry here with sectionField declared
// 3. Add the corresponding field to SectionContent in types.ts
// 4. Run: npm run export-contracts
// Nothing else needs to change.
// ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ

import type { BehaviourMode, SectionContent } from '../src/lib/schema/types';
import { teacherFor } from '../src/lib/teacher/teacher-facing';

export interface ComponentMeta {
	id: string;
	/** Short label for the builder palette */
	teacherLabel: string;
	/** One-sentence description for teachers */
	teacherDescription: string;
	name: string;
	purpose: string;
	cognitiveJob: string;
	subjects: string[];
	behaviourModes: BehaviourMode[];
	shadcnPrimitive: string;
	capacity: Record<string, number | string>;
	printFallback: string;
	/** Guidance for external generators producing this component's section field content */
	generationHint?: string;
	status: 'stable' | 'beta' | 'planned';
	group: 1 | 2 | 3 | 4 | 5 | 6 | 7;
	/**
	 * The field in SectionContent this component reads from.
	 *
	 * null means the component has no dedicated SectionContent block field.
	 * Example: GlossaryInline is used inline in prose ΓÇö it is not a block.
	 *
	 * This is the single source of truth for the component-to-field mapping.
	 * templates/validation.ts and scripts/export-contracts.ts both derive
	 * their maps from this field via getComponentFieldMap().
	 * Never hardcode this mapping anywhere else.
	 */
	sectionField: keyof SectionContent | null;
}

export const legacyBootstrapRegistry: Record<string, ComponentMeta> = {
	// GROUP 1 - FOUNDATION

	SectionHeader: {
		id: 'section-header',
		...teacherFor('section-header'),
		sectionField: 'header',
		name: 'SectionHeader',
		group: 1,
		purpose: 'Opens a section with title, subject, objective, and level indicators',
		cognitiveJob: 'Orient the learner',
		subjects: ['universal'],
		behaviourModes: ['static'],
		shadcnPrimitive: 'Badge (for level pills)',
		capacity: { titleMaxWords: 12, subtitleMaxWords: 20, objectiveMaxWords: 30 },
		printFallback: 'Full static header',
		status: 'stable'
	},

	HookHero: {
		id: 'hook-hero',
		...teacherFor('hook-hero'),
		sectionField: 'hook',
		name: 'HookHero',
		group: 1,
		purpose: 'Creates felt need before explanation arrives',
		cognitiveJob: 'Create felt need',
		subjects: ['universal'],
		behaviourModes: ['static'],
		shadcnPrimitive: 'none - pure layout',
		capacity: { headlineMaxWords: 12, bodyMaxWords: 80 },
		printFallback:
			'Image above headline when present; pull quote block with left border when text-only',
		status: 'stable'
	},

	ExplanationBlock: {
		id: 'explanation-block',
		...teacherFor('explanation-block'),
		sectionField: 'explanation',
		name: 'ExplanationBlock',
		group: 1,
		purpose: 'Sustained prose that builds a mental model',
		cognitiveJob: 'Build understanding',
		subjects: ['universal'],
		behaviourModes: ['static'],
		shadcnPrimitive: 'Typography',
		capacity: { bodyMaxWords: 350, emphasisMax: 3 },
		printFallback: 'Static prose',
		status: 'stable'
	},

	PrerequisiteStrip: {
		id: 'prerequisite-strip',
		...teacherFor('prerequisite-strip'),
		sectionField: 'prerequisites',
		name: 'PrerequisiteStrip',
		group: 1,
		purpose: 'Lists assumed knowledge with optional refresher pop-ups',
		cognitiveJob: 'Activate prior knowledge',
		subjects: ['universal'],
		behaviourModes: ['static', 'hint-toggle'],
		shadcnPrimitive: 'Popover',
		capacity: { itemsMax: 4 },
		printFallback: 'Inline list of prerequisites',
		status: 'stable'
	},

	WhatNextBridge: {
		id: 'what-next-bridge',
		...teacherFor('what-next-bridge'),
		sectionField: 'what_next',
		name: 'WhatNextBridge',
		group: 1,
		purpose: 'Connects the section forward to what the concept enables',
		cognitiveJob: 'Connect forward',
		subjects: ['universal'],
		behaviourModes: ['static'],
		shadcnPrimitive: 'Card',
		capacity: { bodyMaxWords: 50, nextMaxWords: 15, previewMaxWords: 30 },
		printFallback: 'End card with next-lesson label and arrow',
		status: 'stable'
	},

	InterviewAnchor: {
		id: 'interview-anchor',
		...teacherFor('interview-anchor'),
		sectionField: 'interview',
		name: 'InterviewAnchor',
		group: 1,
		purpose: 'Makes knowledge speakable - rehearse explaining the concept',
		cognitiveJob: 'Make knowledge speakable',
		subjects: ['universal'],
		behaviourModes: ['static'],
		shadcnPrimitive: 'Card',
		capacity: { promptMaxWords: 35, audienceMaxWords: 10, followUpMaxWords: 25 },
		printFallback: 'Static with write-in lines',
		status: 'stable'
	},

	CalloutBlock: {
		id: 'callout-block',
		...teacherFor('callout-block'),
		sectionField: 'callout',
		name: 'CalloutBlock',
		group: 1,
		purpose: 'Standalone highlighted callout ΓÇö tip, warning, info, or exam note',
		cognitiveJob: 'Flag what matters',
		subjects: ['universal'],
		behaviourModes: ['static'],
		shadcnPrimitive: 'Alert',
		capacity: { bodyMaxWords: 60, headingMaxWords: 6 },
		printFallback: 'Bordered box; floats as aside when adjacent to explanation, full-width otherwise',
		status: 'stable'
	},

	SummaryBlock: {
		id: 'summary-block',
		...teacherFor('summary-block'),
		sectionField: 'summary',
		name: 'SummaryBlock',
		group: 1,
		purpose: 'Lists what this section covered ΓÇö key takeaways as bullets',
		cognitiveJob: 'Consolidate and close',
		subjects: ['universal'],
		behaviourModes: ['static'],
		shadcnPrimitive: 'Card',
		capacity: { itemsMin: 2, itemsMax: 5, itemMaxWords: 25, closingMaxWords: 30 },
		printFallback: 'Bulleted list with border',
		status: 'stable'
	},

	SectionDivider: {
		id: 'section-divider',
		...teacherFor('section-divider'),
		sectionField: 'divider',
		name: 'SectionDivider',
		group: 1,
		purpose: 'Named visual break between parts within a section',
		cognitiveJob: 'Signal a phase change',
		subjects: ['universal'],
		behaviourModes: ['static'],
		shadcnPrimitive: 'Separator',
		capacity: { labelMaxWords: 4 },
		printFallback: 'Horizontal rule with label',
		status: 'stable'
	},

	// GROUP 2 - DEFINITION AND KNOWLEDGE

	DefinitionCard: {
		id: 'definition-card',
		...teacherFor('definition-card'),
		sectionField: 'definition',
		name: 'DefinitionCard',
		group: 2,
		purpose: 'Anchors a formal term with formal and plain versions',
		cognitiveJob: 'Anchor formal knowledge',
		subjects: ['universal'],
		behaviourModes: ['static', 'plain-formal-toggle'],
		shadcnPrimitive: 'Card + Collapsible',
		capacity: { formalMaxWords: 80, plainMaxWords: 60, relatedTermsMax: 3 },
		printFallback: 'Both versions shown',
		status: 'stable'
	},

	DefinitionFamily: {
		id: 'definition-family',
		...teacherFor('definition-family'),
		sectionField: 'definition_family',
		name: 'DefinitionFamily',
		group: 2,
		purpose: 'Groups related terms that belong together conceptually',
		cognitiveJob: 'Distinguish related concepts',
		subjects: ['universal'],
		behaviourModes: ['static', 'accordion'],
		shadcnPrimitive: 'Card + Accordion',
		capacity: { definitionsMax: 4, introMaxWords: 40 },
		printFallback: 'Horizontal card strip when 4 or fewer terms; vertical list when more',
		status: 'stable'
	},

	GlossaryRail: {
		id: 'glossary-rail',
		...teacherFor('glossary-rail'),
		sectionField: 'glossary',
		name: 'GlossaryRail',
		group: 2,
		purpose: 'Vocabulary visible in peripheral field, updates by section',
		cognitiveJob: 'Retrieve meaning without losing place',
		subjects: ['universal'],
		behaviourModes: ['sticky', 'drawer', 'inline-strip'],
		shadcnPrimitive: 'Card + ScrollArea + Sheet',
		capacity: { termsMax: 8, termsWarning: 6, definitionMaxWords: 30 },
		printFallback: 'Compact inline term strip with bold terms and inline definitions',
		status: 'stable'
	},

	GlossaryInline: {
		id: 'glossary-inline',
		...teacherFor('glossary-inline'),
		sectionField: null, // inline in prose ΓÇö no dedicated SectionContent block field
		name: 'GlossaryInline',
		group: 2,
		purpose: 'In-text definition pop-up on a defined term',
		cognitiveJob: 'Retrieve meaning in context',
		subjects: ['universal'],
		behaviourModes: ['hint-toggle'],
		shadcnPrimitive: 'Popover',
		capacity: { definitionMaxWords: 30 },
		printFallback: 'Term underlined, definition in footnote',
		status: 'stable'
	},

	InsightStrip: {
		id: 'insight-strip',
		...teacherFor('insight-strip'),
		sectionField: 'insight_strip',
		name: 'InsightStrip',
		group: 2,
		purpose: 'Side-by-side comparison of 2-3 related values or concepts',
		cognitiveJob: 'Compare values simultaneously',
		subjects: ['universal'],
		behaviourModes: ['static'],
		shadcnPrimitive: 'CSS Grid',
		capacity: { cellsMax: 3, cellsMin: 2, cellLinesMax: 2 },
		printFallback: 'Horizontal metric cards with top accent border',
		status: 'stable'
	},

	KeyFact: {
		id: 'key-fact',
		...teacherFor('key-fact'),
		sectionField: 'key_fact',
		name: 'KeyFact',
		group: 2,
		purpose: 'Visually prominent stat, formula, or date that anchors the section',
		cognitiveJob: 'Anchor a critical fact',
		subjects: ['universal'],
		behaviourModes: ['static'],
		shadcnPrimitive: 'Card',
		capacity: { factMaxWords: 20, contextMaxWords: 30 },
		printFallback: 'Centred equation display when formula present; bold bordered fact box otherwise',
		status: 'stable'
	},

	ComparisonGrid: {
		id: 'comparison-grid',
		...teacherFor('comparison-grid'),
		sectionField: 'comparison_grid',
		name: 'ComparisonGrid',
		group: 2,
		purpose: 'Holds multiple concepts in view so distinctions become structural',
		cognitiveJob: 'Compare and classify in parallel',
		subjects: ['universal'],
		behaviourModes: ['static'],
		shadcnPrimitive: 'CSS Grid + Card',
		capacity: { columnsMin: 2, columnsMax: 4, rowsMax: 6, criterionMaxWords: 8, valueMaxWords: 20 },
		printFallback: 'Static comparison table',
		status: 'stable'
	},

	// GROUP 3 - EXAMPLES AND PROCESS

	WorkedExampleCard: {
		id: 'worked-example-card',
		...teacherFor('worked-example-card'),
		sectionField: 'worked_example',
		name: 'WorkedExampleCard',
		group: 3,
		purpose: 'Shows reasoning in action step by step, each step justified',
		cognitiveJob: 'Watch reasoning in action',
		subjects: ['universal'],
		behaviourModes: ['static', 'step-reveal', 'accordion', 'compare'],
		shadcnPrimitive: 'Card + Collapsible',
		capacity: { stepsMax: 6, stepsWarning: 4, stepLabelMaxWords: 12, stepContentMaxWords: 80 },
		printFallback: 'Bordered card with numbered step indicators, all steps expanded',
		status: 'stable'
	},

	ProcessSteps: {
		id: 'process-steps',
		...teacherFor('process-steps'),
		sectionField: 'process',
		name: 'ProcessSteps',
		group: 3,
		purpose: 'A repeatable procedure where order is non-negotiable',
		cognitiveJob: 'Follow a procedure',
		subjects: ['universal'],
		behaviourModes: ['static', 'step-reveal'],
		shadcnPrimitive: 'Card + Separator',
		capacity: { stepsMax: 8, actionMaxWords: 15, detailMaxWords: 60 },
		printFallback: 'All steps visible, checkbox squares for print',
		status: 'stable'
	},

	// GROUP 4 - ASSESSMENT AND PRACTICE

	PracticeStack: {
		id: 'practice-stack',
		...teacherFor('practice-stack'),
		sectionField: 'practice',
		name: 'PracticeStack',
		group: 4,
		purpose: 'Problems at calibrated difficulty with progressive hints and optional solutions',
		cognitiveJob: 'Apply understanding under calibrated difficulty',
		subjects: ['universal'],
		behaviourModes: ['hint-toggle', 'accordion', 'progressive-hints', 'flat-list'],
		shadcnPrimitive: 'Accordion + Collapsible',
		capacity: {
			problemsMin: 2,
			problemsMax: 5,
			hintsPerProblemMax: 3,
			questionMaxWords: 100,
			hintMaxWords: 60
		},
		printFallback: 'All visible, write-in lines rendered; inline answers hidden by default',
		status: 'stable'
	},

	QuizCheck: {
		id: 'quiz-check',
		...teacherFor('quiz-check'),
		sectionField: 'quiz',
		name: 'QuizCheck',
		group: 4,
		purpose: 'Quick concept check with immediate feedback mid-section',
		cognitiveJob: 'Verify understanding immediately',
		subjects: ['universal'],
		behaviourModes: ['static'],
		shadcnPrimitive: 'Card + Button',
		capacity: { optionsMin: 3, optionsMax: 4, questionMaxWords: 60, optionMaxWords: 20 },
		printFallback: 'Question and options shown, correct answer marked',
		status: 'stable'
	},

	ReflectionPrompt: {
		id: 'reflection-prompt',
		...teacherFor('reflection-prompt'),
		sectionField: 'reflection',
		name: 'ReflectionPrompt',
		group: 4,
		purpose: 'Pauses forward motion and turns attention inward',
		cognitiveJob: 'Pause and consolidate',
		subjects: ['universal'],
		behaviourModes: ['static'],
		shadcnPrimitive: 'Card',
		capacity: { promptMaxWords: 40, spaceMax: 6 },
		printFallback: 'Prompt with write-in lines',
		status: 'stable'
	},

	StudentTextbox: {
		id: 'student-textbox',
		...teacherFor('student-textbox'),
		sectionField: 'student_textbox',
		name: 'StudentTextbox',
		group: 4,
		purpose: 'Simple write-in box for student responses ΓÇö no framing beyond a prompt',
		cognitiveJob: 'Record thinking',
		subjects: ['universal'],
		behaviourModes: ['static'],
		shadcnPrimitive: 'Textarea (print: lined box)',
		capacity: { promptMaxWords: 40, linesMax: 10 },
		printFallback: 'Lined write-in area',
		status: 'stable'
	},

	ShortAnswerQuestion: {
		id: 'short-answer',
		...teacherFor('short-answer'),
		sectionField: 'short_answer',
		name: 'ShortAnswerQuestion',
		group: 4,
		purpose: 'Open question with write-in space and optional mark scheme',
		cognitiveJob: 'Recall and explain in own words',
		subjects: ['universal'],
		behaviourModes: ['static'],
		shadcnPrimitive: 'Card + Collapsible (mark scheme)',
		capacity: { questionMaxWords: 60, linesMax: 10, marksMax: 10 },
		printFallback: 'Question with lined answer space, mark allocation shown',
		status: 'stable'
	},

	FillInTheBlank: {
		id: 'fill-in-blank',
		...teacherFor('fill-in-blank'),
		sectionField: 'fill_in_blank',
		name: 'FillInTheBlank',
		group: 4,
		purpose: 'Cloze passage with student-completed blanks ΓÇö tests recall not recognition',
		cognitiveJob: 'Retrieve and complete',
		subjects: ['universal'],
		behaviourModes: ['static', 'hint-toggle'],
		shadcnPrimitive: 'Input inline',
		capacity: { segmentsMax: 60, blanksMax: 10, wordBankMax: 15 },
		printFallback: 'Passage with underlined blanks, word bank box below',
		status: 'stable'
	},

	// GROUP 5 - ALERTS

	PitfallAlert: {
		id: 'pitfall-alert',
		...teacherFor('pitfall-alert'),
		sectionField: 'pitfall',
		name: 'PitfallAlert',
		group: 5,
		purpose: 'Names a specific misconception before the learner makes it',
		cognitiveJob: 'Inoculate against error',
		subjects: ['universal'],
		behaviourModes: ['static', 'hint-toggle'],
		shadcnPrimitive: 'Alert + Collapsible',
		capacity: { misconceptionMaxWords: 20, correctionMaxWords: 80, exampleMaxWords: 40 },
		printFallback: 'Bordered warning box with icon and misconception/correction structure',
		status: 'stable'
	},

	// GROUP 6 - DIAGRAMS

	DiagramBlock: {
		id: 'diagram-block',
		...teacherFor('diagram-block'),
		sectionField: 'diagram',
		name: 'DiagramBlock',
		group: 6,
		purpose: 'Makes spatial or relational structure visible',
		cognitiveJob: 'See the structure',
		subjects: ['universal'],
		behaviourModes: ['static', 'zoom', 'hint-toggle'],
		shadcnPrimitive: 'Card + Dialog',
		capacity: { calloutsMax: 6, captionMaxWords: 60 },
		printFallback: 'Static SVG 80% width centred',
		generationHint:
			'Write a caption that precisely describes the visual ΓÇö name every labeled element, the relationship or structure being shown, and what the student should notice first. Use present tense. Max 60 words. A good caption works as a standalone description of the image: someone reading it knows exactly what is drawn without having read the section. Do not describe the topic in general terms ΓÇö describe what is visible.',
		status: 'stable'
	},

	DiagramCompare: {
		id: 'diagram-compare',
		...teacherFor('diagram-compare'),
		sectionField: 'diagram_compare',
		name: 'DiagramCompare',
		group: 6,
		purpose: 'Before and after comparison with a drag slider',
		cognitiveJob: 'See transformation',
		subjects: ['history', 'science', 'mathematics', 'geography'],
		behaviourModes: ['compare'],
		shadcnPrimitive: 'Slider',
		capacity: { captionMaxWords: 60 },
		printFallback: 'Both diagrams shown side by side',
		generationHint:
			'Write a caption that precisely names what is being compared, what is visible in each state, and exactly what changes between them ΓÇö name the specific element that transforms, not just that a change occurs. Use present tense. Max 60 words. The caption must describe both images as if the student cannot see the labels: name the before state, name the after state, name the difference.',
		status: 'stable'
	},

	DiagramSeries: {
		id: 'diagram-series',
		...teacherFor('diagram-series'),
		sectionField: 'diagram_series',
		name: 'DiagramSeries',
		group: 6,
		purpose: 'A progression of diagrams that tells a sequence',
		cognitiveJob: 'Follow a visual progression',
		subjects: ['universal'],
		behaviourModes: ['step-reveal', 'static'],
		shadcnPrimitive: 'Tabs or step nav',
		capacity: { diagramsMax: 4 },
		printFallback: 'All diagrams in sequence with step labels',
		generationHint:
			'Write a series title that describes the full progression shown across all steps, and a caption for each step that names the specific state of the diagram at that moment ΓÇö what is drawn, what has changed from the previous step, and what the student should be able to see. Use present tense throughout. Each step caption must stand alone as a description of that frame: someone reading it knows exactly what that step shows. Max 60 words per caption. Do not repeat the step label as the caption.',
		status: 'stable'
	},

	VideoEmbed: {
		id: 'video-embed',
		...teacherFor('video-embed'),
		sectionField: 'video_embed',
		name: 'VideoEmbed',
		group: 1,
		purpose: 'Embeds a video with caption and print fallback',
		cognitiveJob: 'Engage through multimedia',
		subjects: ['universal'],
		behaviourModes: ['static'],
		shadcnPrimitive: 'iframe',
		capacity: { captionMaxWords: 40 },
		printFallback: 'QR code or thumbnail based on setting',
		status: 'stable'
	},

	ImageBlock: {
		id: 'image-block',
		...teacherFor('image-block'),
		sectionField: 'image_block',
		name: 'ImageBlock',
		group: 6,
		purpose: 'Uploaded raster image with caption and layout options',
		cognitiveJob: 'Illustrate with photos or screenshots',
		subjects: ['universal'],
		behaviourModes: ['static'],
		shadcnPrimitive: 'Card + img',
		capacity: { captionMaxWords: 40, altMaxWords: 80 },
		printFallback: 'Static image from embedded data',
		status: 'stable'
	},

	TimelineBlock: {
		id: 'timeline-block',
		...teacherFor('timeline-block'),
		sectionField: 'timeline',
		name: 'TimelineBlock',
		group: 6,
		purpose: 'Turns chronology into a readable instructional spine',
		cognitiveJob: 'Follow cause and sequence over time',
		subjects: ['history', 'science', 'universal'],
		behaviourModes: ['static', 'timeline-scrubber'],
		shadcnPrimitive: 'Card + Button',
		capacity: { eventsMin: 3, eventsMax: 8, titleMaxWords: 10, summaryMaxWords: 50 },
		printFallback: 'Vertical event list',
		status: 'stable'
	},

	// GROUP 7 - SIMULATION

	SimulationBlock: {
		id: 'simulation-block',
		...teacherFor('simulation-block'),
		sectionField: 'simulation',
		name: 'SimulationBlock',
		group: 7,
		purpose: 'Manipulate a variable and discover the concept through observation',
		cognitiveJob: 'Manipulate and discover',
		subjects: ['mathematics', 'physics', 'chemistry', 'statistics'],
		behaviourModes: ['static'],
		shadcnPrimitive: 'iframe sandbox',
		capacity: { countGuidance: 'template-defined' },
		printFallback: 'Static diagram at midstate',
		status: 'beta'
	}
};
