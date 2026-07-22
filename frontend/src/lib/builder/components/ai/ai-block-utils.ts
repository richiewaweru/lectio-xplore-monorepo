import { getEditSchema, getEmptyContent } from 'lectio';

const MANUAL_ONLY_COMPONENT_IDS = new Set(['image-block', 'video-embed']);

/** Mirrors the backend guard for media blocks that require teacher-provided assets. */
export function isAiGeneratableComponent(componentId: string): boolean {
	return !MANUAL_ONLY_COMPONENT_IDS.has(componentId) && getEditSchema(componentId) !== null;
}

/** True when block content is not the default empty shape (shows Improve in AI UI). */
export function blockHasDistinctContent(
	componentId: string,
	content: Record<string, unknown>
): boolean {
	return JSON.stringify(content) !== JSON.stringify(getEmptyContent(componentId));
}

/** Apply AI output only to non-hidden edit-schema fields to avoid clobbering advanced/internal fields. */
export function mergeAiContentWithEditableFields(
	componentId: string,
	currentContent: Record<string, unknown>,
	generatedContent: Record<string, unknown>
): Record<string, unknown> {
	const schema = getEditSchema(componentId);
	if (!schema) {
		return { ...currentContent };
	}
	const editableFields = new Set(
		schema.fields.filter((field) => field.input !== 'hidden').map((field) => field.field)
	);
	const next: Record<string, unknown> = { ...currentContent };
	for (const [key, value] of Object.entries(generatedContent)) {
		if (editableFields.has(key)) {
			next[key] = value;
		}
	}
	return next;
}
