/**
 * Svelte 5 rune store for LearnDocument editing.
 * Pure mutations live in document-state.ts; attempts stay outside node content.
 */

import {
	addNode as addNodeToDoc,
	addParagraph as addParagraphToDoc,
	deleteNode as deleteNodeFromDoc,
	findNodeIndex,
	moveNodeDown as moveNodeDownInDoc,
	moveNodeUp as moveNodeUpInDoc,
	updateCallout as updateCalloutInDoc,
	updateFigure as updateFigureInDoc,
	updateHeading as updateHeadingInDoc,
	updateListItems as updateListItemsInDoc,
	updateNodeText as updateNodeTextInDoc,
	updateTable as updateTableInDoc,
	type AddableKind
} from './document-state';
import type {
	CalloutTone,
	InteractionAttemptState,
	LearnDocument
} from './types';

export interface LearnDocumentStore {
	readonly document: LearnDocument | null;
	readonly selectedNodeId: string | null;
	readonly attemptsByInteractionId: ReadonlyMap<string, InteractionAttemptState>;
	readonly dirty: boolean;
	loadDocument: (doc: LearnDocument) => void;
	selectNode: (nodeId: string | null) => void;
	updateNodeText: (nodeId: string, text: string) => boolean;
	updateListItems: (nodeId: string, items: string[]) => boolean;
	updateHeading: (
		nodeId: string,
		patch: { text?: string; level?: 1 | 2 | 3 }
	) => boolean;
	updateCallout: (
		nodeId: string,
		patch: { body?: string; title?: string; tone?: CalloutTone }
	) => boolean;
	updateFigure: (
		nodeId: string,
		patch: { caption?: string; alt?: string; asset_id?: string | null }
	) => boolean;
	updateTable: (
		nodeId: string,
		patch: { headers?: string[]; rows?: string[][]; caption?: string }
	) => boolean;
	moveNodeUp: (nodeId: string) => boolean;
	moveNodeDown: (nodeId: string) => boolean;
	addParagraph: (text?: string, afterNodeId?: string | null) => string | null;
	addNode: (kind: AddableKind, afterNodeId?: string | null) => string | null;
	deleteNode: (nodeId: string) => boolean;
	markClean: () => void;
	setAttempt: (attempt: InteractionAttemptState) => void;
	clearAttempts: () => void;
}

export function createLearnDocumentStore(): LearnDocumentStore {
	let document = $state<LearnDocument | null>(null);
	let selectedNodeId = $state<string | null>(null);
	let attemptsByInteractionId = $state<Map<string, InteractionAttemptState>>(new Map());
	let dirty = $state(false);

	function apply(next: LearnDocument | null): boolean {
		if (!next) return false;
		document = next;
		dirty = true;
		return true;
	}

	function insertedId(next: LearnDocument, afterNodeId?: string | null): string | null {
		const inserted =
			afterNodeId != null
				? next.nodes[findNodeIndex(next, afterNodeId) + 1]
				: next.nodes[next.nodes.length - 1];
		return inserted?.id ?? null;
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
		get dirty() {
			return dirty;
		},
		loadDocument(doc: LearnDocument) {
			document = structuredClone(doc);
			selectedNodeId = null;
			attemptsByInteractionId = new Map();
			dirty = false;
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
		updateHeading(nodeId, patch) {
			if (!document) return false;
			return apply(updateHeadingInDoc(document, nodeId, patch));
		},
		updateCallout(nodeId, patch) {
			if (!document) return false;
			return apply(updateCalloutInDoc(document, nodeId, patch));
		},
		updateFigure(nodeId, patch) {
			if (!document) return false;
			return apply(updateFigureInDoc(document, nodeId, patch));
		},
		updateTable(nodeId, patch) {
			if (!document) return false;
			return apply(updateTableInDoc(document, nodeId, patch));
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
			const id = insertedId(next, afterNodeId);
			document = next;
			dirty = true;
			selectedNodeId = id;
			return id;
		},
		addNode(kind: AddableKind, afterNodeId?: string | null) {
			if (!document) return null;
			const next = addNodeToDoc(document, kind, afterNodeId);
			const id = insertedId(next, afterNodeId);
			document = next;
			dirty = true;
			selectedNodeId = id;
			return id;
		},
		deleteNode(nodeId: string) {
			if (!document) return false;
			const ok = apply(deleteNodeFromDoc(document, nodeId));
			if (ok && selectedNodeId === nodeId) selectedNodeId = null;
			return ok;
		},
		markClean() {
			dirty = false;
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
