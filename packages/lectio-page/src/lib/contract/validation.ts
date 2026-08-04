import Ajv2020 from 'ajv/dist/2020.js';
import type { ErrorObject } from 'ajv';
import schema from '../../../contracts/lectio-document-v2.schema.json';
import type {
	AsideContent,
	ChoicesContent,
	DocumentBlock,
	FigureContent,
	LectioDocument,
	ListContent,
	Placement,
	QuestionsContent,
	TableContent
} from './document';
import type { IntentId, PageObject } from './intents';
import { isCompatible } from '../catalogue/compatibility';
import { getObject } from '../catalogue/objects';
import { visibleText, wordCount } from '../utils/rich-text';

export interface ValidationIssue {
	path: string;
	code: string;
	message: string;
	severity: 'error' | 'warning';
}

const ajv = new Ajv2020({
	allErrors: true,
	strict: false
});

const validateStructureAjv = ajv.compile(schema);

function issue(
	path: string,
	code: string,
	message: string,
	severity: 'error' | 'warning' = 'error'
): ValidationIssue {
	return { path, code, message, severity };
}

function ajvPath(err: ErrorObject): string {
	const base = err.instancePath?.replace(/^\//, '').replace(/\//g, '.') ?? '';
	if (err.params && 'missingProperty' in err.params) {
		const missing = String((err.params as { missingProperty: string }).missingProperty);
		return base ? `${base}.${missing}` : missing;
	}
	return base;
}

/** Structural validation against the exported Draft 2020-12 schema. */
export function validateStructure(doc: unknown): ValidationIssue[] {
	if (doc == null || typeof doc !== 'object') {
		return [issue('', 'not-object', 'Document must be an object')];
	}
	const ok = validateStructureAjv(doc);
	if (ok) return [];
	const errors = validateStructureAjv.errors ?? [];
	return errors.map((err) =>
		issue(ajvPath(err), 'schema', err.message ?? 'Schema validation failed')
	);
}

const SAFE_SRC = /^(https?:\/\/|\/|\.\/|\.\.\/|[a-zA-Z0-9_@-])/i;

function isSafeAssetUrl(src: string): boolean {
	const trimmed = src.trim();
	if (!trimmed) return false;
	if (/^(javascript|vbscript|file|data):/i.test(trimmed)) return false;
	return SAFE_SRC.test(trimmed);
}

function collectQuestionIds(doc: LectioDocument): Set<string> {
	const ids = new Set<string>();
	for (const section of doc.sections) {
		for (const block of section.blocks) {
			if (block.object === 'questions') {
				for (const item of block.content.items) ids.add(item.id);
			}
			if (block.object === 'choices') {
				ids.add(block.id);
			}
		}
	}
	return ids;
}

function placementAllowed(object: PageObject, placement: Placement | undefined): boolean {
	if (!placement) return true;
	const record = getObject(object);
	if (!record) return false;
	return record.placement.includes(placement);
}

/** Cross-block and pedagogical rules on a schema-valid document. */
export function validateSemantics(doc: LectioDocument): ValidationIssue[] {
	const issues: ValidationIssue[] = [];
	const sectionIds = new Set<string>();
	const blockIds = new Set<string>();
	const questionIds = new Set<string>();

	for (let si = 0; si < doc.sections.length; si++) {
		const section = doc.sections[si];
		const sp = `sections[${si}]`;

		if (sectionIds.has(section.id)) {
			issues.push(issue(`${sp}.id`, 'duplicate-section-id', `Duplicate section id ${section.id}`));
		} else {
			sectionIds.add(section.id);
		}

		let asideCount = 0;
		const blocks = section.blocks;
		const asideMax = getObject('aside')?.capacity?.maxPerSection;

		for (let bi = 0; bi < blocks.length; bi++) {
			const block = blocks[bi];
			const bp = `${sp}.blocks[${bi}]`;
			validateBlockSemantics(block, bp, bi, blocks, issues, blockIds, questionIds);
			if (block.object === 'aside') asideCount += 1;
		}

		if (asideMax != null && asideCount > asideMax) {
			issues.push(
				issue(
					`${sp}.blocks`,
					'aside-density',
					`Section has ${asideCount} asides; catalogue maxPerSection is ${asideMax}`,
					'warning'
				)
			);
		}
	}

	if (doc.answer_key) {
		validateAnswerKey(doc.answer_key, 'answer_key', issues, blockIds, collectQuestionIds(doc));
	}

	return issues;
}

function validateBlockSemantics(
	block: DocumentBlock,
	bp: string,
	index: number,
	blocks: DocumentBlock[],
	issues: ValidationIssue[],
	blockIds: Set<string>,
	questionIds: Set<string>
): void {
	if (blockIds.has(block.id)) {
		issues.push(issue(`${bp}.id`, 'duplicate-block-id', `Duplicate block id ${block.id}`));
	} else {
		blockIds.add(block.id);
	}

	if (!Number.isInteger(block.position)) {
		issues.push(issue(`${bp}.position`, 'position-type', 'Position must be an integer'));
	} else if (block.position !== index) {
		issues.push(
			issue(
				`${bp}.position`,
				'position-mismatch',
				`Committed position ${block.position} must equal array index ${index}`
			)
		);
	}

	const placement = block.layout?.placement;
	if (placement && !placementAllowed(block.object, placement)) {
		issues.push(
			issue(
				`${bp}.layout.placement`,
				'layout-placement',
				`Placement "${placement}" is not allowed for ${block.object}`
			)
		);
	}

	if (block.object === 'heading') {
		if (block.intent != null) {
			issues.push(
				issue(
					`${bp}.intent`,
					'heading-intent',
					'Heading is structural and must not carry a pedagogical intent'
				)
			);
		}
		const next = blocks[index + 1];
		if (!next) {
			issues.push(
				issue(bp, 'heading-trailing', 'Heading cannot be the final block in a section')
			);
		} else if (next.object === 'heading') {
			issues.push(issue(bp, 'heading-consecutive', 'Consecutive headings are not allowed'));
		} else if (next.object === 'aside' && next.layout?.placement === 'margin') {
			issues.push(
				issue(
					bp,
					'heading-margin-aside',
					'Heading must bind to a substantive next block, not a margin-only aside'
				)
			);
		}
		return;
	}

	const intent = block.intent as IntentId;
	if (block.object === 'answer-key') {
		if (intent !== 'answer-key') {
			issues.push(
				issue(`${bp}.intent`, 'answer-key-intent', 'answer-key blocks must use intent "answer-key"')
			);
		}
	} else if (!isCompatible(block.object, intent)) {
		issues.push(
			issue(
				bp,
				'intent-incompatible',
				`Intent ${intent} is incompatible with object ${block.object}`
			)
		);
	}

	switch (block.object) {
		case 'aside':
			validateAside(block.content, bp, issues);
			break;
		case 'figure':
			validateFigure(block.content, bp, issues);
			break;
		case 'list':
			validateList(block.content, bp, issues);
			break;
		case 'table':
			validateTable(block.content, bp, issues);
			break;
		case 'choices':
			validateChoices(block.content, bp, issues);
			break;
		case 'questions':
			validateQuestions(block.content, bp, issues, questionIds);
			break;
		default:
			break;
	}
}

function validateList(content: ListContent, bp: string, issues: ValidationIssue[]): void {
	const itemsMin = getObject('list')?.capacity?.itemsMin;
	if (itemsMin != null && content.items.length < itemsMin) {
		issues.push(
			issue(
				`${bp}.content.items`,
				'list-too-short',
				`List has ${content.items.length} items; catalogue itemsMin is ${itemsMin}`,
				'warning'
			)
		);
	}
}

function validateAside(content: AsideContent, bp: string, issues: ValidationIssue[]): void {
	const count = wordCount(content.body);
	if (count > 120) {
		issues.push(
			issue(
				`${bp}.content.body`,
				'aside-word-count',
				`Aside visible word count is ${count}; maximum is 120`
			)
		);
	}
}

function validateFigure(content: FigureContent, bp: string, issues: ValidationIssue[]): void {
	const asset = content.asset;
	const status = asset.status ?? (asset.src || asset.svg ? 'ready' : 'pending');
	if (status === 'ready') {
		if (!asset.src && !asset.svg) {
			issues.push(
				issue(`${bp}.content.asset`, 'figure-ready-source', 'Ready figure requires src or svg')
			);
		}
		if (asset.src && !isSafeAssetUrl(asset.src)) {
			issues.push(
				issue(`${bp}.content.asset.src`, 'figure-unsafe-url', 'Figure src uses an unsafe protocol')
			);
		}
	} else if (status === 'pending') {
		if (!asset.request_id) {
			issues.push(
				issue(
					`${bp}.content.asset.request_id`,
					'figure-pending-id',
					'Pending figure requires request_id'
				)
			);
		}
	}
}

function validateTable(content: TableContent, bp: string, issues: ValidationIssue[]): void {
	const capacity = getObject('table')?.capacity;
	const columnsMin = capacity?.columnsMin;
	const rowsMin = capacity?.rowsMin;
	if (columnsMin != null && content.columns.length < columnsMin) {
		issues.push(
			issue(
				`${bp}.content.columns`,
				'table-too-narrow',
				`Table has ${content.columns.length} columns; catalogue columnsMin is ${columnsMin}`,
				'warning'
			)
		);
	}
	if (rowsMin != null && content.rows.length < rowsMin) {
		issues.push(
			issue(
				`${bp}.content.rows`,
				'table-too-short',
				`Table has ${content.rows.length} rows; catalogue rowsMin is ${rowsMin}`,
				'warning'
			)
		);
	}

	const colIds = new Set<string>();
	for (let ci = 0; ci < content.columns.length; ci++) {
		const id = content.columns[ci].id;
		if (colIds.has(id)) {
			issues.push(
				issue(`${bp}.content.columns[${ci}].id`, 'table-column-id', `Duplicate column id ${id}`)
			);
		} else {
			colIds.add(id);
		}
	}
	for (let ri = 0; ri < content.rows.length; ri++) {
		const cells = content.rows[ri].cells;
		for (const key of Object.keys(cells)) {
			if (!colIds.has(key)) {
				issues.push(
					issue(
						`${bp}.content.rows[${ri}].cells`,
						'table-cell-column',
						`Cell key "${key}" is not a declared column`
					)
				);
			}
		}
		for (const id of colIds) {
			if (!(id in cells)) {
				issues.push(
					issue(
						`${bp}.content.rows[${ri}].cells`,
						'table-missing-cell',
						`Row is missing cell for column "${id}"`,
						'warning'
					)
				);
			}
		}
	}
}

function validateChoices(content: ChoicesContent, bp: string, issues: ValidationIssue[]): void {
	const optionsMin = getObject('choices')?.capacity?.optionsMin;
	if (optionsMin != null && content.options.length < optionsMin) {
		issues.push(
			issue(
				`${bp}.content.options`,
				'choices-too-few',
				`Choices has ${content.options.length} options; catalogue optionsMin is ${optionsMin}`,
				'warning'
			)
		);
	}

	const letters = new Set<string>();
	for (let oi = 0; oi < content.options.length; oi++) {
		const opt = content.options[oi];
		const op = `${bp}.content.options[${oi}]`;
		if (letters.has(opt.letter)) {
			issues.push(issue(`${op}.letter`, 'choices-letter', `Duplicate option letter ${opt.letter}`));
		} else {
			letters.add(opt.letter);
		}
		if (!visibleText(opt.text).trim()) {
			issues.push(issue(`${op}.text`, 'choices-empty', 'Choice option text must not be empty'));
		}
	}
}

function validateQuestions(
	content: QuestionsContent,
	bp: string,
	issues: ValidationIssue[],
	questionIds: Set<string>
): void {
	for (let qi = 0; qi < content.items.length; qi++) {
		const item = content.items[qi];
		if (questionIds.has(item.id)) {
			issues.push(
				issue(`${bp}.content.items[${qi}].id`, 'duplicate-question-id', `Duplicate question id ${item.id}`)
			);
		} else {
			questionIds.add(item.id);
		}
	}
}

function validateAnswerKey(
	block: DocumentBlock,
	bp: string,
	issues: ValidationIssue[],
	blockIds: Set<string>,
	knownQuestions: Set<string>
): void {
	if (block.object !== 'answer-key') {
		issues.push(issue(bp, 'answer-key-object', 'Document answer_key must be an answer-key block'));
		return;
	}
	if (blockIds.has(block.id)) {
		issues.push(issue(`${bp}.id`, 'duplicate-block-id', `Duplicate block id ${block.id}`));
	} else {
		blockIds.add(block.id);
	}
	if (block.intent !== 'answer-key') {
		issues.push(
			issue(`${bp}.intent`, 'answer-key-intent', 'answer-key blocks must use intent "answer-key"')
		);
	}
	const placement = block.layout?.placement;
	if (placement && !placementAllowed('answer-key', placement)) {
		issues.push(
			issue(
				`${bp}.layout.placement`,
				'layout-placement',
				`Placement "${placement}" is not allowed for answer-key`
			)
		);
	}

	const seen = new Set<string>();
	for (let gi = 0; gi < block.content.groups.length; gi++) {
		const group = block.content.groups[gi];
		for (let ei = 0; ei < group.entries.length; ei++) {
			const entry = group.entries[ei];
			const ep = `${bp}.content.groups[${gi}].entries[${ei}]`;
			if (seen.has(entry.question_id)) {
				issues.push(
					issue(
						`${ep}.question_id`,
						'answer-key-duplicate',
						`Duplicate answer entry for ${entry.question_id}`
					)
				);
			} else {
				seen.add(entry.question_id);
			}
			if (!knownQuestions.has(entry.question_id)) {
				issues.push(
					issue(
						`${ep}.question_id`,
						'answer-key-ref',
						`No question or choices block with id ${entry.question_id}`
					)
				);
			}
		}
	}
}

export function validateDocument(doc: unknown): ValidationIssue[] {
	const structural = validateStructure(doc);
	if (structural.some((i) => i.severity === 'error')) {
		return structural;
	}
	return [...structural, ...validateSemantics(doc as LectioDocument)];
}

export function assertValidDocument(doc: unknown): asserts doc is LectioDocument {
	const issues = validateDocument(doc).filter((i) => i.severity === 'error');
	if (issues.length > 0) {
		const summary = issues.map((i) => `${i.path}: [${i.code}] ${i.message}`).join('; ');
		throw new Error(`Invalid LectioDocument: ${summary}`);
	}
}
