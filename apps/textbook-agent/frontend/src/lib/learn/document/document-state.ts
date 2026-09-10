/**
 * LearnDocument v2 store helpers — mutate by stable node id.
 * Runtime attempt state stays outside document.nodes content.
 */

import type { LearnDocument, LearnNode, ListNode, ParagraphNode } from './types';

export type ReorderDirection = 'up' | 'down';

function stamp(doc: LearnDocument): LearnDocument {
	return { ...doc, updated_at: new Date().toISOString() };
}

function cloneNodes(nodes: LearnNode[]): LearnNode[] {
	return nodes.map((n) => ({ ...n }));
}

export function findNodeIndex(doc: LearnDocument, nodeId: string): number {
	return doc.nodes.findIndex((n) => n.id === nodeId);
}

/** Replace a node by id; returns null if missing. */
export function replaceNode(
	doc: LearnDocument,
	nodeId: string,
	next: LearnNode
): LearnDocument | null {
	const index = findNodeIndex(doc, nodeId);
	if (index < 0) return null;
	const nodes = cloneNodes(doc.nodes);
	nodes[index] = next;
	return stamp({ ...doc, nodes });
}

/**
 * Update primary text on paragraph / heading / callout / list item text fields.
 * For lists, `text` is ignored — use `updateListItems`.
 */
export function updateNodeText(
	doc: LearnDocument,
	nodeId: string,
	text: string
): LearnDocument | null {
	const index = findNodeIndex(doc, nodeId);
	if (index < 0) return null;
	const node = doc.nodes[index];
	let next: LearnNode;
	switch (node.kind) {
		case 'paragraph':
		case 'heading':
			next = { ...node, text };
			break;
		case 'callout':
			next = { ...node, body: text };
			break;
		case 'interaction':
			next = { ...node, prompt: text };
			break;
		case 'figure':
			next = { ...node, caption: text };
			break;
		case 'table':
			next = { ...node, caption: text };
			break;
		case 'list':
			return null;
		default:
			return null;
	}
	return replaceNode(doc, nodeId, next);
}

export function updateListItems(
	doc: LearnDocument,
	nodeId: string,
	items: string[]
): LearnDocument | null {
	const index = findNodeIndex(doc, nodeId);
	if (index < 0) return null;
	const node = doc.nodes[index];
	if (node.kind !== 'list') return null;
	const next: ListNode = { ...node, items: items.map(String) };
	return replaceNode(doc, nodeId, next);
}

export function reorderNode(
	doc: LearnDocument,
	nodeId: string,
	direction: ReorderDirection
): LearnDocument | null {
	const index = findNodeIndex(doc, nodeId);
	if (index < 0) return null;
	const target = direction === 'up' ? index - 1 : index + 1;
	if (target < 0 || target >= doc.nodes.length) return doc;
	const nodes = cloneNodes(doc.nodes);
	const tmp = nodes[index]!;
	nodes[index] = nodes[target]!;
	nodes[target] = tmp;
	return stamp({ ...doc, nodes });
}

export function moveNodeUp(doc: LearnDocument, nodeId: string): LearnDocument | null {
	return reorderNode(doc, nodeId, 'up');
}

export function moveNodeDown(doc: LearnDocument, nodeId: string): LearnDocument | null {
	return reorderNode(doc, nodeId, 'down');
}

function newNodeId(prefix = 'node'): string {
	if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
		return `${prefix}_${crypto.randomUUID()}`;
	}
	return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export function addParagraph(
	doc: LearnDocument,
	text = 'New paragraph',
	afterNodeId?: string | null
): LearnDocument {
	const paragraph: ParagraphNode = {
		id: newNodeId('p'),
		kind: 'paragraph',
		text
	};
	const nodes = cloneNodes(doc.nodes);
	if (afterNodeId) {
		const index = nodes.findIndex((n) => n.id === afterNodeId);
		if (index >= 0) {
			nodes.splice(index + 1, 0, paragraph);
			return stamp({ ...doc, nodes });
		}
	}
	nodes.push(paragraph);
	return stamp({ ...doc, nodes });
}

export function deleteNode(doc: LearnDocument, nodeId: string): LearnDocument | null {
	const index = findNodeIndex(doc, nodeId);
	if (index < 0) return null;
	const nodes = cloneNodes(doc.nodes);
	nodes.splice(index, 1);
	return stamp({ ...doc, nodes });
}
