/**
 * LearnDocument v2 TypeScript types — mirrors backend
 * `learn.contracts.lesson_document` + `document.models`.
 */

export const DOCUMENT_PRIMITIVE_KINDS = [
	'paragraph',
	'heading',
	'list',
	'figure',
	'table',
	'callout',
	'equation',
	'quote',
	'compare'
] as const;

export type DocumentPrimitiveKind = (typeof DOCUMENT_PRIMITIVE_KINDS)[number];

export const RETAINED_INTERACTION_TYPES = [
	'choice',
	'multi-select',
	'fill-blank',
	'classify',
	'match-pairs',
	'sequence',
	'numeric',
	'short-response'
] as const;

export type InteractionType = (typeof RETAINED_INTERACTION_TYPES)[number];

export type CalloutTone = 'note' | 'warning' | 'tip' | 'important';
export type CalloutVariant = 'key_idea' | 'note' | 'misconception';

interface NodeBase {
	id: string;
	teaching_block_id?: string | null;
}

export interface ParagraphNode extends NodeBase {
	kind: 'paragraph';
	text: string;
}

export interface HeadingNode extends NodeBase {
	kind: 'heading';
	text: string;
	level?: 1 | 2 | 3;
}

export interface ListNode extends NodeBase {
	kind: 'list';
	ordered?: boolean;
	items: string[];
}

export interface FigureNode extends NodeBase {
	kind: 'figure';
	asset_id?: string | null;
	caption?: string;
	alt?: string;
	/** Set when media generation was exhausted: render a placeholder instead of an image. */
	status?: 'unavailable';
	unavailable_reason?: string;
}

export interface TableNode extends NodeBase {
	kind: 'table';
	headers?: string[];
	rows?: string[][];
	caption?: string;
}

export interface CalloutNode extends NodeBase {
	kind: 'callout';
	tone?: CalloutTone;
	title?: string;
	body?: string;
	variant?: CalloutVariant | null;
	belief?: string | null;
	evidence?: string | null;
	conclusion?: string | null;
	aside?: string | null;
}

export interface EquationNode extends NodeBase {
	kind: 'equation';
	label?: string | null;
	inputs: string[];
	condition?: string | null;
	outputs: string[];
}

export interface QuoteNode extends NodeBase {
	kind: 'quote';
	text: string;
	attribution?: string | null;
}

export interface CompareItem {
	label?: string | null;
	title: string;
	body: string;
}

export interface CompareNode extends NodeBase {
	kind: 'compare';
	items: CompareItem[];
}

export type DocumentNode =
	| ParagraphNode
	| HeadingNode
	| ListNode
	| FigureNode
	| TableNode
	| CalloutNode
	| EquationNode
	| QuoteNode
	| CompareNode;
export interface InteractionNode extends NodeBase {
	kind: 'interaction';
	interaction_type: InteractionType;
	prompt?: string;
	config?: Record<string, unknown>;
	feedback?: Record<string, unknown> | string | null;
	assessment_mode?: string | null;
	attempt_policy?: Record<string, unknown> | null;
	completion?: Record<string, unknown> | string | null;
	role?: 'predict' | 'practice' | 'check' | null;
	display_prompt?: string | null;
	option_notes?: Record<string, string> | null;
	/** Full authored contract for evaluate/reload. */
	contract?: Record<string, unknown> | null;
}

export type LearnNode = DocumentNode | InteractionNode;

export interface LearnSection {
	id: string;
	title?: string;
	position: number;
	transition?: string | null;
	node_ids?: string[];
}

export interface LearnDocument {
	version: 2;
	id: string;
	title: string;
	subject: string;
	source: string;
	source_generation_id?: string | null;
	nodes: LearnNode[];
	sections?: LearnSection[];
	created_at: string;
	updated_at: string;
	teaching_plan_id?: string | null;
	teaching_plan_revision?: number | null;
}

/** Runtime attempt state — kept outside node content. */
export interface InteractionAttemptState {
	interactionId: string;
	outcome?: string;
	feedback?: string;
	response?: Record<string, unknown>;
	score_earned?: number;
	score_possible?: number;
}

export function isLearnDocument(value: unknown): value is LearnDocument {
	return (
		typeof value === 'object' &&
		value !== null &&
		(value as { version?: unknown }).version === 2 &&
		Array.isArray((value as { nodes?: unknown }).nodes)
	);
}

export function isDocumentNode(node: LearnNode): node is DocumentNode {
	return node.kind !== 'interaction';
}

export function isInteractionNode(node: LearnNode): node is InteractionNode {
	return node.kind === 'interaction';
}
