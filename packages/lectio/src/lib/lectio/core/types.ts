import type { ZodTypeAny } from 'zod';

import type { TeachingIntent } from '$lib/schema/component-meta';
import type { BehaviourMode } from '$lib/schema/types';
import type { LectioContentContract } from './content-contract';

export type LectioPhase = 1 | 2 | 3 | 4 | 5 | 6 | 7;

export type ComponentStatus = 'stable' | 'beta' | 'planned';

/** Fragmentation / grouping contract for print layout and preflight */
export type PrintBreakBehavior = 'atomic' | 'itemized' | 'table' | 'prose';

export type PrintPreferredWidth = 'full' | 'half' | 'third' | 'content-fit' | 'inline' | 'aside';

export type PrintMediaConstraint = 'constrain-height' | 'constrain-width' | 'fit-cell';

export interface LectioCapabilities {
	acceptsMedia: boolean;
	acceptsQuestions: boolean;
	producesAnswerKey: boolean;
	interactive: boolean;
	isMedia: boolean;
}

export interface LectioPrintSpec {
	breakBehavior: PrintBreakBehavior;
	/** CSS selector for itemized children (required when breakBehavior is itemized) */
	itemSelector?: string;
	preferredWidth: PrintPreferredWidth;
	/** Optional max height hint (px) for preflight / tooling */
	maxPrintHeight?: number;
	hasMedia: boolean;
	mediaConstraint?: PrintMediaConstraint;
	/** When true, print theme applies aggressive color/background reset on this subtree */
	requiresColorReset: boolean;
	/** Mirrors legacy registry `printFallback` / pipeline `print_fallback` */
	fallback: string;
	notes?: string;
}

/** V3-facing metadata carried alongside legacy `ComponentMeta` fields during migration */
export interface LectioComponentPublicMetadata {
	id: string;
	name: string;
	phase: LectioPhase;

	/** Agent-readable structural role (lesson-plan rules live elsewhere) */
	role: string;

	cognitiveJob: string;
	subjects: readonly string[];
	behaviourModes: readonly BehaviourMode[];

	capabilities: LectioCapabilities;
	capacity: Record<string, number | string>;

	status: ComponentStatus;

	/**
	 * Field on SectionContent that this component renders.
	 * `null` for inline-only components (omit from component-field-map).
	 */
	sectionField: string | null;

	generationHint?: string;
	shadcnPrimitive: string;

	/** Registry object key (`SectionHeader`, `WorkedExampleCard`, â€¦) â€” stable importer surface */
	registryKey: string;

	/** Shared vocabulary for builder palette grouping + planning alignment */
	teachingIntent: TeachingIntent;
}

/** Contract + metadata bundle safe to import from Node exporters (no `.svelte`) */
export interface LectioContentModule {
	schema: ZodTypeAny;
	metadata: LectioComponentPublicMetadata;
	/**
	 * @deprecated Print layout specs are not part of the `@lectio/learn` public API.
	 * Retained optionally for transitional builders; Page Print uses `@lectio/page`.
	 */
	print?: LectioPrintSpec;
	/** Optional web-native Learn hints (interaction / evaluation / narration / a11y). */
	web?: {
		interaction?: 'none' | 'reveal' | 'input' | 'choice' | 'manipulation' | 'media-control';
		responseEvaluation?: 'none' | 'self-check' | 'auto-score' | 'teacher-review' | 'rubric';
		narration?: 'none' | 'optional' | 'recommended';
		learnerBand?: 'support' | 'core' | 'extend';
		accessibilityNotes?: string;
	};
	examples: unknown[];
	contentContract?: LectioContentContract;
}

/** Optional renderer â€” only bundled in UI builds */
export interface LectioComponentModule extends LectioContentModule {
	component?: unknown;
}
