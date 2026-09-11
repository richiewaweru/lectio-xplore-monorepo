/**
 * LearnDocument v2 store helpers — mutate by stable node id.
 * Runtime attempt state stays outside document.nodes content.
 * teaching_block_id is preserved on updates via object spread.
 */

import type {
	CalloutNode,
	CalloutTone,
	DocumentPrimitiveKind,
	FigureNode,
	HeadingNode,
	LearnDocument,
	LearnNode,
	ListNode,
	ParagraphNode,
	TableNode
} from './types';

export type ReorderDirection = 'up' | 'down';

export type AddableKind = DocumentPrimitiveKind;

function stamp(doc: LearnDocument): LearnDocument {
	return { ...doc, updated_at: new Date().toISOString() };
}

function cloneNodes(nodes: LearnNode[]): LearnNode[] {
	return nodes.map((n) => ({ ...n }));
}

export function findNodeIndex(doc: LearnDocument, nodeId: string): number {
	return doc.nodes.findIndex((n) => n.id === nodeId);
}

/** Replace a node by id; returns null if missing. Preserves identity when callers spread. */
export function replaceNode(
	doc: LearnDocument,
	nodeId: string,
	next: LearnNode
): LearnDocument | null {
	const index = findNodeIndex(doc, nodeId);
	if (index < 0) return null;
	const nodes = cloneNodes(doc.nodes);
	const prev = nodes[index]!;
	// Keep stable id + teaching_block_id unless the replacement explicitly sets them.
	nodes[index] = {
		...next,
		id: prev.id,
		teaching_block_id:
			next.teaching_block_id !== undefined ? next.teaching_block_id : prev.teaching_block_id
	};
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

export function updateHeading(
	doc: LearnDocument,
	nodeId: string,
	patch: { text?: string; level?: 1 | 2 | 3 }
): LearnDocument | null {
	const index = findNodeIndex(doc, nodeId);
	if (index < 0) return null;
	const node = doc.nodes[index];
	if (node.kind !== 'heading') return null;
	const next: HeadingNode = {
		...node,
		text: patch.text ?? node.text,
		level: patch.level ?? node.level
	};
	return replaceNode(doc, nodeId, next);
}

export function updateCallout(
	doc: LearnDocument,
	nodeId: string,
	patch: { body?: string; title?: string; tone?: CalloutTone }
): LearnDocument | null {
	const index = findNodeIndex(doc, nodeId);
	if (index < 0) return null;
	const node = doc.nodes[index];
	if (node.kind !== 'callout') return null;
	const next: CalloutNode = {
		...node,
		body: patch.body ?? node.body,
		title: patch.title !== undefined ? patch.title : node.title,
		tone: patch.tone ?? node.tone
	};
	return replaceNode(doc, nodeId, next);
}

export function updateFigure(
	doc: LearnDocument,
	nodeId: string,
	patch: { caption?: string; alt?: string; asset_id?: string | null }
): LearnDocument | null {
	const index = findNodeIndex(doc, nodeId);
	if (index < 0) return null;
	const node = doc.nodes[index];
	if (node.kind !== 'figure') return null;
	const next: FigureNode = {
		...node,
		caption: patch.caption !== undefined ? patch.caption : node.caption,
		alt: patch.alt !== undefined ? patch.alt : node.alt,
		asset_id: patch.asset_id !== undefined ? patch.asset_id : node.asset_id
	};
	return replaceNode(doc, nodeId, next);
}

export function updateTable(
	doc: LearnDocument,
	nodeId: string,
	patch: { headers?: string[]; rows?: string[][]; caption?: string }
): LearnDocument | null {
	const index = findNodeIndex(doc, nodeId);
	if (index < 0) return null;
	const node = doc.nodes[index];
	if (node.kind !== 'table') return null;
	const next: TableNode = {
		...node,
		headers: patch.headers !== undefined ? patch.headers.map(String) : node.headers,
		rows:
			patch.rows !== undefined
				? patch.rows.map((row) => row.map(String))
				: node.rows,
		caption: patch.caption !== undefined ? patch.caption : node.caption
	};
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

function createPrimitive(kind: AddableKind): LearnNode {
	const id = newNodeId(kind.slice(0, 3));
	switch (kind) {
		case 'paragraph':
			return { id, kind: 'paragraph', text: 'New paragraph' } satisfies ParagraphNode;
		case 'heading':
			return { id, kind: 'heading', text: 'New heading', level: 2 } satisfies HeadingNode;
		case 'list':
			return {
				id,
				kind: 'list',
				ordered: false,
				items: ['Item 1']
			} satisfies ListNode;
		case 'figure':
			return {
				id,
				kind: 'figure',
				asset_id: null,
				caption: '',
				alt: ''
			} satisfies FigureNode;
		case 'table':
			return {
				id,
				kind: 'table',
				headers: ['Column A', 'Column B'],
				rows: [['', '']],
				caption: ''
			} satisfies TableNode;
		case 'callout':
			return {
				id,
				kind: 'callout',
				tone: 'note',
				title: '',
				body: 'New callout'
			} satisfies CalloutNode;
	}
}

function insertAfter(
	doc: LearnDocument,
	node: LearnNode,
	afterNodeId?: string | null
): LearnDocument {
	const nodes = cloneNodes(doc.nodes);
	if (afterNodeId) {
		const index = nodes.findIndex((n) => n.id === afterNodeId);
		if (index >= 0) {
			nodes.splice(index + 1, 0, node);
			return stamp({ ...doc, nodes });
		}
	}
	nodes.push(node);
	return stamp({ ...doc, nodes });
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
	return insertAfter(doc, paragraph, afterNodeId);
}

/** Add any ordinary primitive after a node (or append). Stable new id; no teaching_block_id. */
export function addNode(
	doc: LearnDocument,
	kind: AddableKind,
	afterNodeId?: string | null
): LearnDocument {
	return insertAfter(doc, createPrimitive(kind), afterNodeId);
}

export function deleteNode(doc: LearnDocument, nodeId: string): LearnDocument | null {
	const index = findNodeIndex(doc, nodeId);
	if (index < 0) return null;
	const nodes = cloneNodes(doc.nodes);
	nodes.splice(index, 1);
	return stamp({ ...doc, nodes });
}
