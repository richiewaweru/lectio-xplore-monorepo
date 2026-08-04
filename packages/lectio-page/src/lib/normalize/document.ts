import type { DocumentBlock, HeadingBlock, LectioDocument, LectioSection } from '../contract/document';

export type SubstantiveBlock = Exclude<DocumentBlock, HeadingBlock>;

/**
 * Order lifecycle:
 * 1. Generation — `position` required; events may arrive out of order.
 * 2. Commit — `normalizeDocument` sorts by position then id, rewrites contiguous indexes.
 * 3. Render — array order is canonical; the renderer must not sort again.
 *
 * `section.title` renders as the section h2 (see SectionView).
 * Nested `heading` blocks remain structural (h3); planners exclude them in the first slice.
 */
export type RenderUnit =
	| {
			kind: 'heading-binding';
			heading: HeadingBlock;
			lead: SubstantiveBlock;
	  }
	| {
			kind: 'block';
			block: SubstantiveBlock;
	  };

/** Build render units from committed array order (no sorting). */
export function buildRenderUnits(blocks: DocumentBlock[]): RenderUnit[] {
	const out: RenderUnit[] = [];
	for (let i = 0; i < blocks.length; i++) {
		const block = blocks[i];
		if (block.object === 'heading') {
			const next = blocks[i + 1];
			if (next && next.object !== 'heading') {
				out.push({
					kind: 'heading-binding',
					heading: block,
					lead: next
				});
				i += 1;
			}
			// Trailing / consecutive headings are omitted here; validateSemantics rejects them.
			continue;
		}
		out.push({ kind: 'block', block });
	}
	return out;
}

export class NormalizeError extends Error {
	constructor(public readonly issues: string[]) {
		super(`Document normalize failed: ${issues.join('; ')}`);
		this.name = 'NormalizeError';
	}
}

/** Sort by position then id; rewrite contiguous indexes. Throws on duplicate block ids. */
export function normalizeDocument(doc: LectioDocument): LectioDocument {
	const seen = new Set<string>();
	const issues: string[] = [];

	const sections = doc.sections.map((section, si) =>
		normalizeSection(section, si, seen, issues)
	);

	let answer_key = doc.answer_key;
	if (answer_key) {
		if (seen.has(answer_key.id)) {
			issues.push(`Duplicate block id ${answer_key.id} (answer_key)`);
		} else {
			seen.add(answer_key.id);
		}
		answer_key = { ...answer_key, position: 0 };
	}

	if (issues.length > 0) {
		throw new NormalizeError(issues);
	}

	return { ...doc, sections, answer_key };
}

function normalizeSection(
	section: LectioSection,
	si: number,
	seen: Set<string>,
	issues: string[]
): LectioSection {
	const blocks = [...section.blocks].sort(
		(a, b) => a.position - b.position || a.id.localeCompare(b.id)
	);

	for (const block of blocks) {
		if (seen.has(block.id)) {
			issues.push(`Duplicate block id ${block.id} in sections[${si}]`);
		} else {
			seen.add(block.id);
		}
	}

	return {
		...section,
		blocks: blocks.map((block, index) => ({ ...block, position: index }) as DocumentBlock)
	};
}

export function stableId(prefix: string, index: number): string {
	return `${prefix}-${index + 1}`;
}
