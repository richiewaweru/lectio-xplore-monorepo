import { getComponentById, validateDocument, type LessonDocument } from 'lectio';

function slugify(text: string): string {
	return text
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-|-$/g, '');
}

/** Trigger download of the current lesson as `.lesson.json` (browser only). */
export function downloadLessonDocument(lesson: LessonDocument): void {
	const json = JSON.stringify(lesson, null, 2);
	const blob = new Blob([json], { type: 'application/json' });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = `${slugify(lesson.title) || 'lesson'}.lesson.json`;
	a.click();
	URL.revokeObjectURL(url);
}

export interface ImportResult {
	success: boolean;
	document?: LessonDocument;
	errors?: string[];
}

export async function importLessonFile(file: File): Promise<ImportResult> {
	try {
		const text = await file.text();
		const parsed: unknown = JSON.parse(text);

		if (typeof parsed !== 'object' || parsed === null) {
			return { success: false, errors: ['File is not a valid JSON object'] };
		}

		const doc = parsed as Record<string, unknown>;

		if (doc.version !== 1) {
			return {
				success: false,
				errors: [`Unsupported document version: ${String(doc.version)}. Expected 1.`]
			};
		}

		const structuralErrors = validateStructure(parsed);
		if (structuralErrors.length > 0) {
			return { success: false, errors: structuralErrors };
		}

		const lesson = parsed as LessonDocument;

		for (const block of Object.values(lesson.blocks)) {
			if (!getComponentById(block.component_id)) {
				return {
					success: false,
					errors: [`Unknown component_id "${block.component_id}" on block "${block.id}".`]
				};
			}
		}

		const validation = validateDocument(lesson);
		if (!validation.valid) {
			return { success: false, errors: validation.errors };
		}

		return { success: true, document: lesson };
	} catch (e) {
		return {
			success: false,
			errors: [e instanceof SyntaxError ? 'Invalid JSON file' : String(e)]
		};
	}
}

function validateStructure(obj: unknown): string[] {
	const errors: string[] = [];
	if (typeof obj !== 'object' || obj === null) {
		return ['File is not a valid JSON object'];
	}
	const doc = obj as Record<string, unknown>;

	for (const field of ['id', 'title', 'subject', 'sections', 'blocks', 'preset_id', 'media'] as const) {
		if (!(field in doc)) {
			errors.push(`Missing required field: ${field}`);
		}
	}

	if (!Array.isArray(doc.sections)) {
		errors.push('sections must be an array');
		return errors;
	}

	if (typeof doc.blocks !== 'object' || doc.blocks === null || Array.isArray(doc.blocks)) {
		errors.push('blocks must be an object');
		return errors;
	}

	const blocks = doc.blocks as Record<string, { component_id?: string }>;

	for (let i = 0; i < doc.sections.length; i++) {
		const sec = doc.sections[i] as Record<string, unknown>;
		if (typeof sec !== 'object' || sec === null) {
			errors.push(`sections[${i}] must be an object`);
			continue;
		}
		if (!Array.isArray(sec.block_ids)) {
			errors.push(`sections[${i}].block_ids must be an array`);
			continue;
		}
		for (const bid of sec.block_ids as string[]) {
			if (!blocks[bid]) {
				errors.push(`sections[${i}] references missing block id "${bid}"`);
			}
		}
	}

	return errors;
}
