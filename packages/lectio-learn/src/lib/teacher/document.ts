import { getComponentById, getComponentFieldMap } from '../schema/registry';
import type { LearnInteractionContract } from '../learn/interaction-contract';
import { validateInteractionContract } from '../learn/interaction-contract';
import { getEmptyContent } from './content-factories';
import { validateSection } from '../schema/validate';
import type { GradeBand, PitfallContent, SectionContent, WorkedExampleContent } from '../schema/types';

/** Reserved component_id prefix for Learn interaction blocks (P06). */
export const LEARN_INTERACTION_COMPONENT_PREFIX = 'learn-interaction:';

/** Portable lesson document format version. Bump on breaking changes. */
export type LessonDocumentVersion = 1;

/** Learner-facing section intent (authored; not runtime state). */
export type LearnerSectionIntent =
	| 'orient'
	| 'explain'
	| 'practice'
	| 'check'
	| 'reflect'
	| 'bridge';

/** How the student shell advances between sections. */
export type SectionNavigationPolicy = 'linear' | 'free' | 'gated';

/** When a section may be considered complete in the shell (policy only — no attempt data). */
export type SectionCompletionPolicy = 'viewed' | 'interacted' | 'submitted' | 'manual';

/** Practice vs graded designation at the section seam. */
export type SectionAssessmentMode = 'practice' | 'graded' | 'ungraded-info';

/**
 * Concept / evidence references authored on the experience seam.
 * Must not include attempt scores, progress flags, or other learner runtime state.
 */
export interface SectionConceptRef {
	concept_id: string;
	evidence_keys?: string[];
	role?: 'introduce' | 'practice' | 'assess' | 'reinforce';
}

export interface BlockInstance {
	id: string;
	component_id: string;
	content: Record<string, unknown>;
	position: number;
	/**
	 * Authored Learn interaction contract when this block is an activity.
	 * Authoritative for evaluation; never reconstructed from SectionContent.
	 */
	learn_interaction?: LearnInteractionContract;
	/** Section-level assessment override for interaction blocks. */
	assessment_mode?: SectionAssessmentMode | 'practice' | 'graded';
	/** Authored concept refs on the block (not learner runtime state). */
	concept_refs?: SectionConceptRef[];
}

export interface DocumentSection {
	id: string;
	template_id: string;
	block_ids: string[];
	title: string;
	position: number;
	/** Short learner-facing label for tabs/stages (defaults to title). */
	learner_label?: string;
	/** Pedagogical intent of this stage for the student shell. */
	learner_intent?: LearnerSectionIntent;
	/** When true, shell treats the stage as required before gated advance. */
	required?: boolean;
	navigation_policy?: SectionNavigationPolicy;
	completion_policy?: SectionCompletionPolicy;
	assessment_mode?: SectionAssessmentMode;
	/** Concept/evidence refs — authored only; never attempt state. */
	concept_refs?: SectionConceptRef[];
}


export interface MediaReference {
	id: string;
	type: 'video' | 'image' | 'audio';
	url: string;
	filename?: string;
	mime_type?: string;
	alt_text?: string;
	print_fallback?: 'thumbnail' | 'qr-link' | 'hide';
}

export interface LessonDocument {
	version: LessonDocumentVersion;
	id: string;
	title: string;
	subject: string;
	description?: string;
	preset_id: string;
	source: 'generated' | 'template' | 'manual';
	source_generation_id?: string;
	grade_band?: GradeBand;
	sections: DocumentSection[];
	blocks: Record<string, BlockInstance>;
	media: Record<string, MediaReference>;
	created_at: string;
	updated_at: string;
	author?: string;
}

export interface DocumentValidationResult {
	valid: boolean;
	errors: string[];
	warnings: string[];
}

export interface FromSectionContentsMetadata {
	title: string;
	subject: string;
	preset_id: string;
	/** Fallback when a section lacks template_id (rare) */
	template_id?: string;
	source?: 'generated' | 'template' | 'manual';
	source_generation_id?: string;
	grade_band?: GradeBand;
}

/**
 * Field name → component registry id. Inverse of getComponentFieldMap().
 * Only keys that map to a block component appear.
 */
export function getFieldComponentMap(): Partial<Record<keyof SectionContent, string>> {
	const forward = getComponentFieldMap();
	const reverse: Partial<Record<keyof SectionContent, string>> = {};
	for (const [componentId, field] of Object.entries(forward)) {
		reverse[field as keyof SectionContent] = componentId;
	}
	return reverse;
}

/** Canonical block order within a section (template lessonFlow removed; this is stable UI order). */
const BLOCK_FIELD_ORDER: (keyof SectionContent)[] = [
	'header',
	'hook',
	'prerequisites',
	'divider',
	'explanation',
	'definition',
	'definition_family',
	'key_fact',
	'callout',
	'insight_strip',
	'comparison_grid',
	'diagram',
	'diagram_compare',
	'diagram_series',
	'video_embed',
	'image_block',
	'timeline',
	'worked_example',
	'worked_examples',
	'process',
	'simulation',
	'pitfall',
	'pitfalls',
	'practice',
	'quiz',
	'answer_key',
	'short_answer',
	'fill_in_blank',
	'student_textbox',
	'reflection',
	'interview',
	'glossary',
	'summary',
	'what_next'
];

function newId(): string {
	if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
		return crypto.randomUUID();
	}
	return `id-${Math.random().toString(36).slice(2, 11)}-${Date.now()}`;
}

function deepClone<T>(value: T): T {
	return structuredClone(value);
}

function extractBlocksFromSection(section: SectionContent): Array<{ componentId: string; content: unknown }> {
	const fieldToComp = getFieldComponentMap();
	const out: Array<{ componentId: string; content: unknown }> = [];

	for (const field of BLOCK_FIELD_ORDER) {
		if (field === 'worked_examples') {
			for (const w of section.worked_examples ?? []) {
				out.push({ componentId: 'worked-example-card', content: w });
			}
			continue;
		}
		if (field === 'pitfalls') {
			for (const p of section.pitfalls ?? []) {
				out.push({ componentId: 'pitfall-alert', content: p });
			}
			continue;
		}

		const val = section[field];
		if (val === undefined || val === null) continue;

		const compId = fieldToComp[field];
		if (!compId) continue;

		out.push({ componentId: compId, content: val });
	}

	return out;
}

/**
 * Decompose SectionContent[] into a LessonDocument.
 * Preserves section_id as DocumentSection.id for stable round-trips.
 */
export function fromSectionContents(
	sections: SectionContent[],
	metadata: FromSectionContentsMetadata
): LessonDocument {
	const blocks: Record<string, BlockInstance> = {};
	const docSections: DocumentSection[] = [];
	const now = new Date().toISOString();
	const source =
		metadata.source ?? (metadata.source_generation_id ? 'generated' : 'template');

	let sectionPosition = 0;
	for (const section of sections) {
		const extracted = extractBlocksFromSection(section);
		const block_ids: string[] = [];
		let blockPos = 0;
		for (const { componentId, content } of extracted) {
			const id = newId();
			block_ids.push(id);
			blocks[id] = {
				id,
				component_id: componentId,
				content: deepClone(content) as Record<string, unknown>,
				position: blockPos++
			};
		}

		docSections.push({
			id: section.section_id,
			template_id: section.template_id || metadata.template_id || 'unknown',
			block_ids,
			title: section.header?.title ?? section.section_id,
			position: sectionPosition++
		});
	}

	return {
		version: 1,
		id: newId(),
		title: metadata.title,
		subject: metadata.subject,
		preset_id: metadata.preset_id,
		source,
		source_generation_id: metadata.source_generation_id,
		grade_band: metadata.grade_band,
		sections: docSections,
		blocks,
		media: {},
		created_at: now,
		updated_at: now
	};
}

function emptySectionShell(docSection: DocumentSection): SectionContent {
	return {
		section_id: docSection.id,
		template_id: docSection.template_id,
		header: getEmptyContent('section-header') as unknown as SectionContent['header'],
		hook: getEmptyContent('hook-hero') as unknown as SectionContent['hook'],
		explanation: getEmptyContent('explanation-block') as unknown as SectionContent['explanation'],
		practice: getEmptyContent('practice-stack') as unknown as SectionContent['practice'],
		what_next: getEmptyContent('what-next-bridge') as unknown as SectionContent['what_next']
	};
}

function applyBlockToSection(
	section: SectionContent,
	componentId: string,
	content: Record<string, unknown>
): void {
	const fieldMap = getComponentFieldMap();

	if (componentId === 'pitfall-alert') {
		const p = content as unknown as PitfallContent;
		if (!section.pitfall) {
			section.pitfall = p;
		} else {
			if (!section.pitfalls) section.pitfalls = [];
			section.pitfalls.push(p);
		}
		return;
	}

	if (componentId === 'worked-example-card') {
		const w = content as unknown as WorkedExampleContent;
		if (!section.worked_example) {
			section.worked_example = w;
		} else {
			if (!section.worked_examples) section.worked_examples = [];
			section.worked_examples.push(w);
		}
		return;
	}

	if (componentId === 'simulation-block') {
		if (!section.simulation) {
			section.simulation = deepClone(content) as unknown as NonNullable<SectionContent['simulation']>;
		}
		return;
	}

	const field = fieldMap[componentId];
	if (!field) return;

	(section as unknown as Record<string, unknown>)[field] = deepClone(content);
}

/**
 * Rebuild SectionContent[] from a LessonDocument.
 *
 * Compatibility contract (P06): this path is **lossy** for repeated same-type
 * blocks and for content→activity→content interleaving — interaction blocks are
 * skipped and duplicate component fields overwrite. Authoritative student/Builder
 * render must use {@link orderedBlocksInSection} / `block_ids` instead.
 */
export function toSectionContents(document: LessonDocument): SectionContent[] {
	const ordered = [...document.sections].sort((a, b) => a.position - b.position);
	return ordered.map((docSection) => {
		const section = emptySectionShell(docSection);
		for (const blockId of docSection.block_ids) {
			const block = document.blocks[blockId];
			if (!block) continue;
			if (isLearnInteractionBlock(block)) continue;
			applyBlockToSection(section, block.component_id, block.content);
		}
		return section;
	});
}

export function isLearnInteractionBlock(block: BlockInstance): boolean {
	if (block.learn_interaction) return true;
	return block.component_id.startsWith(LEARN_INTERACTION_COMPONENT_PREFIX);
}

/** Authoritative ordered blocks for a section — preserves repeats and interleaving. */
export function orderedBlocksInSection(
	document: LessonDocument,
	sectionId: string
): BlockInstance[] {
	const section = orderedDocumentSections(document).find((s) => s.id === sectionId);
	if (!section) return [];
	const out: BlockInstance[] = [];
	for (const blockId of section.block_ids) {
		const block = document.blocks[blockId];
		if (block) out.push(block);
	}
	return out;
}

/** Flatten all sections' block_ids in document order. */
export function orderedBlocksInDocument(document: LessonDocument): BlockInstance[] {
	const out: BlockInstance[] = [];
	for (const section of orderedDocumentSections(document)) {
		for (const blockId of section.block_ids) {
			const block = document.blocks[blockId];
			if (block) out.push(block);
		}
	}
	return out;
}

/**
 * Structural + capacity validation. Structural problems set valid=false.
 */
export function validateDocument(document: LessonDocument): DocumentValidationResult {
	const errors: string[] = [];
	const warnings: string[] = [];

	if (document.version !== 1) {
		errors.push(`Unsupported document version: ${document.version} (expected 1).`);
	}

	for (const key of ['id', 'title', 'subject', 'preset_id', 'sections', 'blocks'] as const) {
		if ((document as unknown as Record<string, unknown>)[key] === undefined) {
			errors.push(`Missing required field: ${key}`);
		}
	}

	if (!document.media) {
		errors.push('Missing required field: media');
	}

	for (const sec of document.sections) {
		let simulationBlockCount = 0;
		for (const bid of sec.block_ids) {
			if (!document.blocks[bid]) {
				errors.push(`Section "${sec.id}" references missing block id "${bid}".`);
			} else if (document.blocks[bid].component_id === 'simulation-block') {
				simulationBlockCount++;
			}
		}
		if (simulationBlockCount > 1) {
			warnings.push(
				`Section "${sec.id}" contains ${simulationBlockCount} simulation-block entries; only the first is loaded.`
			);
		}
	}

	for (const block of Object.values(document.blocks)) {
		if (isLearnInteractionBlock(block)) {
			const contract = block.learn_interaction;
			if (!contract) {
				errors.push(`Interaction block "${block.id}" is missing learn_interaction.`);
			} else {
				for (const msg of validateInteractionContract(contract)) {
					errors.push(`Interaction block "${block.id}": ${msg}`);
				}
			}
			continue;
		}
		if (!getComponentById(block.component_id)) {
			errors.push(`Unknown component_id on block "${block.id}": "${block.component_id}".`);
		}
	}

	if (errors.length > 0) {
		return { valid: false, errors, warnings };
	}

	// Content-only projection for legacy section validators — interactions omitted by design.
	const sections = toSectionContents(document);
	sections.forEach((sec) => {
		const w = validateSection(sec);
		for (const msg of w) {
			warnings.push(`[${sec.section_id}] ${msg}`);
		}
	});

	return { valid: true, errors: [], warnings };
}

/** Canonical ordered sections by `position` then stable `id`. */
export function orderedDocumentSections(document: LessonDocument): DocumentSection[] {
	return [...document.sections].sort((a, b) => {
		if (a.position !== b.position) return a.position - b.position;
		return a.id.localeCompare(b.id);
	});
}

/** Learner tab/stage label — never invents runtime state. */
export function learnerSectionLabel(section: DocumentSection): string {
	const label = section.learner_label?.trim();
	if (label) return label;
	const title = section.title?.trim();
	if (title) return title;
	return `Stage ${section.position + 1}`;
}

/**
 * Apply default learner-facing metadata without mutating attempt/runtime fields.
 * Existing authored values win.
 */
export function withDefaultLearnerSectionMeta(section: DocumentSection): DocumentSection {
	return {
		...section,
		learner_label: learnerSectionLabel(section),
		learner_intent: section.learner_intent ?? 'explain',
		required: section.required ?? true,
		navigation_policy: section.navigation_policy ?? 'linear',
		completion_policy: section.completion_policy ?? 'viewed',
		assessment_mode: section.assessment_mode ?? 'ungraded-info',
		concept_refs: section.concept_refs ?? []
	};
}

/** Strip any accidental learner runtime keys if present on a plain object section. */
const FORBIDDEN_LEARNER_STATE_KEYS = [
	'attempt_id',
	'progress',
	'completed',
	'score',
	'responses',
	'started_at',
	'finished_at'
] as const;

export function assertNoLearnerStateOnSection(section: DocumentSection): string[] {
	const errors: string[] = [];
	const raw = section as unknown as Record<string, unknown>;
	for (const key of FORBIDDEN_LEARNER_STATE_KEYS) {
		if (key in raw && raw[key] !== undefined) {
			errors.push(`Learner runtime key "${key}" must not appear on DocumentSection.`);
		}
	}
	return errors;
}

