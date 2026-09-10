/**
 * Svelte 5 rune store for LearnDocument editing.
 * Pure mutations live in document-state.ts; attempts stay outside node content.
 */

import {
	addParagraph as addParagraphToDoc,
	deleteNode as deleteNodeFromDoc,
	findNodeIndex,
	moveNodeDown as moveNodeDownInDoc,
	moveNodeUp as moveNodeUpInDoc,
	updateListItems as updateListItemsInDoc,
	updateNodeText as updateNodeTextInDoc
} from './document-state';
import type { InteractionAttemptState, LearnDocument } from './types';

export interface LearnDocumentStore {
	readonly document: LearnDocument | null;
	readonly selectedNodeId: string | null;
	readonly attemptsByInteractionId: ReadonlyMap<string, InteractionAttemptState>;
	loadDocument: (doc: LearnDocument) => void;
	selectNode: (nodeId: string | null) => void;
	updateNodeText: (nodeId: string, text: string) => boolean;
	updateListItems: (nodeId: string, items: string[]) => boolean;
	moveNodeUp: (nodeId: string) => boolean;
	moveNodeDown: (nodeId: string) => boolean;
	addParagraph: (text?: string, afterNodeId?: string | null) => string | null;
	deleteNode: (nodeId: string) => boolean;
	setAttempt: (attempt: InteractionAttemptState) => void;
	clearAttempts: () => void;
}

export function createLearnDocumentStore(): LearnDocumentStore {
	let document = $state<LearnDocument | null>(null);
	let selectedNodeId = $state<string | null>(null);
	let attemptsByInteractionId = $state<Map<string, InteractionAttemptState>>(new Map());

	function apply(next: LearnDocument | null): boolean {
		if (!next) return false;
		document = next;
		return true;
	}

	return {
		get document() {
			return document;
		},
		get selectedNodeId() {
			return selectedNodeId;
		},
		get attemptsByInteractionId() {
			return attemptsByInteractionId;
		},
		loadDocument(doc: LearnDocument) {
			document = structuredClone(doc);
			selectedNodeId = null;
			attemptsByInteractionId = new Map();
		},
		selectNode(nodeId: string | null) {
			selectedNodeId = nodeId;
		},
		updateNodeText(nodeId: string, text: string) {
			if (!document) return false;
			return apply(updateNodeTextInDoc(document, nodeId, text));
		},
		updateListItems(nodeId: string, items: string[]) {
			if (!document) return false;
			return apply(updateListItemsInDoc(document, nodeId, items));
		},
		moveNodeUp(nodeId: string) {
			if (!document) return false;
			return apply(moveNodeUpInDoc(document, nodeId));
		},
		moveNodeDown(nodeId: string) {
			if (!document) return false;
			return apply(moveNodeDownInDoc(document, nodeId));
		},
		addParagraph(text = 'New paragraph', afterNodeId?: string | null) {
			if (!document) return null;
			const next = addParagraphToDoc(document, text, afterNodeId);
			const inserted =
				afterNodeId != null
					? next.nodes[findNodeIndex(next, afterNodeId) + 1]
					: next.nodes[next.nodes.length - 1];
			document = next;
			selectedNodeId = inserted?.id ?? null;
			return inserted?.id ?? null;
		},
		deleteNode(nodeId: string) {
			if (!document) return false;
			const ok = apply(deleteNodeFromDoc(document, nodeId));
			if (ok && selectedNodeId === nodeId) selectedNodeId = null;
			return ok;
		},
		setAttempt(attempt: InteractionAttemptState) {
			const next = new Map(attemptsByInteractionId);
			next.set(attempt.interactionId, attempt);
			attemptsByInteractionId = next;
		},
		clearAttempts() {
			attemptsByInteractionId = new Map();
		}
	};
}
