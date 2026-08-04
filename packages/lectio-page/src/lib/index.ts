export type {
	LectioDocument,
	DocumentBlock,
	IntentId,
	PageObject,
	AnswerKeyBlock,
	HeadingBlock
} from './contract';
export type { ValidationIssue } from './contract/validation';
export {
	PAGE_OBJECTS,
	INTENT_IDS,
	assertValidDocument,
	validateDocument,
	validateSemantics,
	validateStructure
} from './contract';
export { listIntents, listObjects, isCompatible, getIntent, getObject } from './catalogue';
export { normalizeDocument, buildRenderUnits, NormalizeError } from './normalize/document';
export type { RenderUnit, SubstantiveBlock } from './normalize/document';
export { default as LectioDocumentView } from './render/LectioDocumentView.svelte';
export { default as ReviewDocumentView } from './review/ReviewDocumentView.svelte';
