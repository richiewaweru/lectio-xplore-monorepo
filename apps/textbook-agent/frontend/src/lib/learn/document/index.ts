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
	addNode,
	addParagraph,
	deleteNode,
	findNodeIndex,
	moveNodeDown,
	moveNodeUp,
	reorderNode,
	replaceNode,
	updateCallout,
	updateFigure,
	updateHeading,
	updateListItems,
	updateNodeText,
	updateTable,
	type AddableKind,
	type ReorderDirection
} from './document-state';

export {
	createLearnDocumentStore,
	type LearnDocumentStore
} from './document-state.svelte';

export { resolveAssetUrl, type AssetRef } from './resolve-asset';

export { default as DocumentCanvas } from './DocumentCanvas.svelte';
export { default as DocumentEditor } from './DocumentEditor.svelte';
export { default as DocumentNodeRenderer } from './renderers/DocumentNodeRenderer.svelte';
export { default as InteractionNodeRenderer } from './renderers/InteractionNodeRenderer.svelte';
export { default as ParagraphEditor } from './editors/ParagraphEditor.svelte';
export { default as ListEditor } from './editors/ListEditor.svelte';
export { default as HeadingEditor } from './editors/HeadingEditor.svelte';
export { default as CalloutEditor } from './editors/CalloutEditor.svelte';
export { default as FigureEditor } from './editors/FigureEditor.svelte';
export { default as TableEditor } from './editors/TableEditor.svelte';
