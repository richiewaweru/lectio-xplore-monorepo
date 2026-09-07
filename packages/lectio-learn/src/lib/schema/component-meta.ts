import type { BehaviourMode, SectionContent } from './types';

export type TeachingIntent =
	| 'explain'
	| 'define'
	| 'show-how'
	| 'practice'
	| 'reflect'
	| 'warn'
	| 'visualize'
	| 'structure'
	| 'engage';

/** Web-native Learn interaction hints (Phase 02). Optional; never required for render. */
export type InteractionKind =
	| 'none'
	| 'reveal'
	| 'input'
	| 'choice'
	| 'manipulation'
	| 'media-control';

export type ResponseEvaluation =
	| 'none'
	| 'self-check'
	| 'auto-score'
	| 'teacher-review'
	| 'rubric';

export type NarrationRole = 'none' | 'optional' | 'recommended';

export type LearnerBand = 'support' | 'core' | 'extend';

export interface WebLearnHints {
	interaction?: InteractionKind;
	responseEvaluation?: ResponseEvaluation;
	narration?: NarrationRole;
	learnerBand?: LearnerBand;
	accessibilityNotes?: string;
}

/** Legacy Lectio palette + contract metadata consumed by builders and exporters */
export interface ComponentMeta {
	id: string;
	/** Short label for the builder palette */
	teacherLabel: string;
	/** One-sentence description for teachers */
	teacherDescription: string;
	teachingIntent: TeachingIntent;
	name: string;
	purpose: string;
	cognitiveJob: string;
	subjects: string[];
	behaviourModes: BehaviourMode[];
	shadcnPrimitive: string;
	capacity: Record<string, number | string>;
	/**
	 * @deprecated Print product is owned by `@lectio/page`. Kept optional for
	 * transitional Component Lectio print chrome only; not part of the Learn public contract.
	 */
	printFallback?: string;
	/** Optional web-native Learn metadata (interaction / evaluation / a11y). */
	web?: WebLearnHints;
	/** Guidance for external generators producing this component's section field content */
	generationHint?: string;
	status: 'stable' | 'beta' | 'planned';
	group: 1 | 2 | 3 | 4 | 5 | 6 | 7;
	/**
	 * Field in SectionContent this component renders.
	 *
	 * null means inline-only usage (no dedicated SectionContent column).
	 */
	sectionField: keyof SectionContent | null;
}
