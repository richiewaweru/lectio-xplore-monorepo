import type { IntentId, PageObject } from './intents';

/** Restrained typed inline nodes. Raw HTML is forbidden. */
export type InlineNode =
	| { type: 'text'; value: string }
	| { type: 'strong'; children: InlineNode[] }
	| { type: 'emphasis'; children: InlineNode[] }
	| { type: 'small-caps'; children: InlineNode[] }
	| { type: 'term'; value: string; definition?: string }
	| { type: 'math'; latex: string }
	| { type: 'reference'; target_id: string; label: string };

export type RichText = InlineNode[];
export type RichParagraph = { children: InlineNode[] };

export type Placement = 'main' | 'margin' | 'spanning';

export interface LayoutHint {
	placement?: Placement;
}

/**
 * Generic block base. Heading uses TIntent = undefined (structural; no pedagogical intent).
 */
export interface BlockBase<
	TObject extends PageObject,
	TContent,
	TIntent extends IntentId | undefined = IntentId
> {
	id: string;
	object: TObject;
	position: number;
	content: TContent;
	intent: TIntent;
	role?: string;
	layout?: LayoutHint;
}

export interface HeadingContent {
	level: 1 | 2 | 3 | '1' | '2' | '3';
	text: string;
	number?: string | null;
}

export interface ProseContent {
	paragraphs: RichParagraph[] | string[];
}

export interface ListItem {
	text: RichText | string;
}

export interface ListContent {
	style: 'ordered' | 'unordered' | 'steps' | 'glossary';
	lead_in?: RichText | string | null;
	items: ListItem[];
}

export interface TableColumn {
	id: string;
	label: string;
}

export interface TableRow {
	cells: Record<string, RichText | string>;
}

export interface TableContent {
	columns: TableColumn[];
	rows: TableRow[];
	caption?: string | null;
	presentation?: 'standard' | 'comparison' | 'timeline';
}

export interface FigureAsset {
	kind?: 'image' | 'svg';
	src?: string;
	svg?: string;
	status?: 'ready' | 'pending' | 'failed';
	request_id?: string;
}

export interface FigureContent {
	asset: FigureAsset;
	caption?: string | null;
	alt_text: string;
	width?: 'main' | 'span';
}

export interface AsideContent {
	label?: string | null;
	body: RichText | string;
}

export interface WorkedStep {
	text: RichText | string;
}

export interface WorkedExampleContent {
	title?: string | null;
	problem: RichText | string;
	steps: WorkedStep[];
	answer: RichText | string;
	check?: RichText | string | null;
}

export interface QuestionItem {
	id: string;
	prompt: RichText | string;
	marks?: number | null;
	answer_lines?: number;
}

export interface QuestionsContent {
	items: QuestionItem[];
	instructions?: RichText | string | null;
}

export interface ChoiceOption {
	letter: string;
	text: RichText | string;
}

export interface ChoicesContent {
	stem: RichText | string;
	options: ChoiceOption[];
	marks?: number | null;
}

export interface AnswerEntry {
	question_id: string;
	answer: RichText | string;
	alternatives?: Array<RichText | string>;
	working?: RichText | string | null;
	rubric?: RichText | string | null;
}

export interface AnswerGroup {
	title?: string | null;
	entries: AnswerEntry[];
}

export interface AnswerKeyContent {
	groups: AnswerGroup[];
}

/** Heading is structural page furniture — no pedagogical intent. */
export type HeadingBlock = BlockBase<'heading', HeadingContent, undefined>;

export type ProseBlock = BlockBase<'prose', ProseContent>;
export type ListBlock = BlockBase<'list', ListContent>;
export type TableBlock = BlockBase<'table', TableContent>;
export type FigureBlock = BlockBase<'figure', FigureContent>;
export type AsideBlock = BlockBase<'aside', AsideContent>;
export type WorkedExampleBlock = BlockBase<'worked-example', WorkedExampleContent>;
export type QuestionsBlock = BlockBase<'questions', QuestionsContent>;
export type ChoicesBlock = BlockBase<'choices', ChoicesContent>;
export type AnswerKeyBlock = BlockBase<'answer-key', AnswerKeyContent, 'answer-key'>;

export type DocumentBlock =
	| HeadingBlock
	| ProseBlock
	| ListBlock
	| TableBlock
	| FigureBlock
	| AsideBlock
	| WorkedExampleBlock
	| QuestionsBlock
	| ChoicesBlock
	| AnswerKeyBlock;

export interface LectioSection {
	id: string;
	title: string;
	blocks: DocumentBlock[];
}

export interface FrontMatter {
	cover?: boolean;
	contents?: boolean;
	running_head?: string | null;
	fields?: string[];
}

export interface DocumentMetadata {
	school?: string;
	teacher?: string;
	date?: string;
	[key: string]: unknown;
}

export interface LectioDocument {
	document_version: 2;
	contract_version: string;
	id: string;
	title: string;
	language: string;
	subject?: string;
	audience?: Record<string, unknown>;
	metadata: DocumentMetadata;
	front_matter?: FrontMatter;
	sections: LectioSection[];
	answer_key?: AnswerKeyBlock;
}
