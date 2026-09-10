export type {
	CalloutNode,
	CalloutTone,
	DocumentNode,
	DocumentPrimitiveKind,
	FigureNode,
	HeadingNode,
	InteractionAttemptState,
	InteractionNode,
	InteractionType,
	LearnDocument,
	LearnNode,
	ListNode,
	ParagraphNode,
	TableNode
} from './types';

export {
	DOCUMENT_PRIMITIVE_KINDS,
	RETAINED_INTERACTION_TYPES,
	isDocumentNode,
	isInteractionNode,
	isLearnDocument
} from './types';

export {
	addParagraph,
	deleteNode,
	findNodeIndex,
	moveNodeDown,
	moveNodeUp,
	reorderNode,
	replaceNode,
	updateListItems,
	updateNodeText,
	type ReorderDirection
} from './document-state';

export {
	createLearnDocumentStore,
	type LearnDocumentStore
} from './document-state.svelte';

export { default as DocumentCanvas } from './DocumentCanvas.svelte';
export { default as DocumentNodeRenderer } from './renderers/DocumentNodeRenderer.svelte';
export { default as InteractionNodeRenderer } from './renderers/InteractionNodeRenderer.svelte';
export { default as ParagraphEditor } from './editors/ParagraphEditor.svelte';
export { default as ListEditor } from './editors/ListEditor.svelte';
