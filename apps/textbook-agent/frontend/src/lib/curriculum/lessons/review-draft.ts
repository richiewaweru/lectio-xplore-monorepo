/** Pure helpers for the SharedLessonDocument reviewer path (no I/O here). */

export type SharedNodeKind =
	| 'paragraph'
	| 'heading'
	| 'list'
	| 'figure'
	| 'table'
	| 'callout'
	| 'equation'
	| 'quote'
	| 'compare'
	| 'task_anchor';

export interface SharedNodeAccessibility {
	description?: string;
	alt_text?: string;
}

export interface SharedParagraphDisplay {
	text: string;
}

export interface SharedHeadingDisplay {
	text: string;
	level?: number;
}

export interface SharedListDisplay {
	ordered?: boolean;
	items: string[];
}

export interface SharedFigureDisplay {
	asset_id?: string | null;
	caption?: string;
}

export interface SharedTableDisplay {
	headers?: string[];
	rows?: string[][];
	caption?: string;
}

export interface SharedCalloutDisplay {
	tone?: 'note' | 'warning' | 'tip' | 'important';
	title?: string;
	body?: string | null;
	variant?: 'key_idea' | 'note' | 'misconception' | null;
	belief?: string | null;
	evidence?: string | null;
	conclusion?: string | null;
	aside?: string | null;
}

export interface SharedEquationDisplay {
	label?: string | null;
	inputs: string[];
	condition?: string | null;
	outputs: string[];
}

export interface SharedQuoteDisplay {
	text: string;
	attribution?: string | null;
}

export interface SharedCompareItem {
	label?: string | null;
	title: string;
	body: string;
}

export interface SharedCompareDisplay {
	items: SharedCompareItem[];
}

export interface SharedNode {
	id: string;
	kind: SharedNodeKind;
	teaching_block_id?: string | null;
	task_spec_id?: string;
	role?: string | null;
	display?:
		| SharedParagraphDisplay
		| SharedHeadingDisplay
		| SharedListDisplay
		| SharedFigureDisplay
		| SharedTableDisplay
		| SharedCalloutDisplay
		| SharedEquationDisplay
		| SharedQuoteDisplay
		| SharedCompareDisplay;
	accessibility?: SharedNodeAccessibility;
}

export interface SharedSection {
	id: string;
	title: string;
	position: number;
	nodes: SharedNode[];
}

export interface SharedTaskOption {
	id: string;
	text: string;
	[key: string]: unknown;
}

/** The reviewer-visible slice of a SharedTaskSpec (the answer key is never edited). */
export interface SharedTask {
	id: string;
	action: string;
	prompt: string;
	role?: 'predict' | 'practice' | 'check' | null;
	display_prompt?: string | null;
	response: { type?: string; options?: SharedTaskOption[]; [key: string]: unknown };
	feedback?: Record<string, unknown> | null;
	option_notes?: Record<string, string> | null;
	[key: string]: unknown;
}

export interface SharedLessonDocument {
	schema_version: number;
	id: string;
	revision: number;
	content_hash: string;
	title: string;
	sections: SharedSection[];
	tasks?: SharedTask[];
	[key: string]: unknown;
}

export interface ContinuityIssue {
	issue_code: string;
	affected_section_id: string;
	affected_node_ids: string[];
	explanation: string;
	required_correction: string;
}

export type ReviewEditField =
	| 'text'
	| 'callout_title'
	| 'callout_body'
	| 'figure_caption'
	| 'figure_alt_text'
	| 'list_item_text'
	| 'table_cell_text'
	| 'accessibility_description'
	| 'task_prompt'
	| 'task_option_text'
	| 'task_feedback_text';

export interface ReviewDraftTextEdit {
	section_id: string;
	node_id: string;
	field: ReviewEditField;
	value: string;
	item_index?: number;
	row_index?: number;
	column_index?: number;
	option_id?: string;
	feedback_key?: string;
}

/** One reviewer-editable slot in the document, with its current value. */
export interface EditableField {
	key: string;
	section_id: string;
	node_id: string;
	node_kind: SharedNodeKind;
	field: ReviewEditField;
	item_index?: number;
	row_index?: number;
	column_index?: number;
	option_id?: string;
	feedback_key?: string;
	label: string;
	value: string;
}

/** A stable identity for one editable slot, independent of its current value. */
export interface EditableFieldTarget {
	section_id: string;
	node_id: string;
	field: ReviewEditField;
	item_index?: number;
	row_index?: number;
	column_index?: number;
	option_id?: string;
	feedback_key?: string;
}

export function fieldKey(target: EditableFieldTarget): string {
	return [
		target.section_id,
		target.node_id,
		target.field,
		target.item_index ?? '',
		target.row_index ?? '',
		target.column_index ?? '',
		target.option_id ?? '',
		target.feedback_key ?? ''
	].join('::');
}

/** Response types whose option *text* is editable (the key references option ids). */
const TEXT_EDITABLE_RESPONSE_TYPES = new Set(['single_choice', 'multiple_choice']);

const FEEDBACK_LABELS: Record<string, string> = {
	correct: 'Feedback when correct',
	incorrect: 'Feedback when incorrect',
	partial: 'Feedback when partly correct'
};

/** Flatten string feedback messages to dotted keys (e.g. ``by_option.b``). */
function feedbackEntries(
	feedback: Record<string, unknown> | null | undefined,
	prefix = ''
): Array<[string, string]> {
	if (!feedback) return [];
	const entries: Array<[string, string]> = [];
	for (const [key, value] of Object.entries(feedback)) {
		const path = prefix ? `${prefix}.${key}` : key;
		if (typeof value === 'string') entries.push([path, value]);
		else if (value && typeof value === 'object' && !Array.isArray(value)) {
			entries.push(...feedbackEntries(value as Record<string, unknown>, path));
		}
	}
	return entries;
}

function feedbackLabel(path: string): string {
	if (FEEDBACK_LABELS[path]) return FEEDBACK_LABELS[path];
	const option = path.startsWith('by_option.') ? path.slice('by_option.'.length) : null;
	return option ? `Feedback for option ${option}` : `Feedback (${path})`;
}

/** Editable wording for the task behind one task anchor. The answer key is never offered. */
export function editableTaskFields(
	sectionId: string,
	anchor: SharedNode,
	task: SharedTask
): EditableField[] {
	const base = { section_id: sectionId, node_id: anchor.id, node_kind: anchor.kind };
	const fields: EditableField[] = [
		{
			...base,
			key: fieldKey({ section_id: sectionId, node_id: anchor.id, field: 'task_prompt' }),
			field: 'task_prompt',
			label: 'Question prompt',
			value: task.prompt ?? ''
		}
	];
	if (TEXT_EDITABLE_RESPONSE_TYPES.has(String(task.response?.type ?? ''))) {
		for (const option of task.response.options ?? []) {
			fields.push({
				...base,
				key: fieldKey({
					section_id: sectionId,
					node_id: anchor.id,
					field: 'task_option_text',
					option_id: option.id
				}),
				field: 'task_option_text',
				option_id: option.id,
				label: `Option ${option.id}`,
				value: option.text ?? ''
			});
		}
	}
	for (const [path, value] of feedbackEntries(task.feedback)) {
		fields.push({
			...base,
			key: fieldKey({
				section_id: sectionId,
				node_id: anchor.id,
				field: 'task_feedback_text',
				feedback_key: path
			}),
			field: 'task_feedback_text',
			feedback_key: path,
			label: feedbackLabel(path),
			value
		});
	}
	return fields;
}

const ISSUE_LABELS: Record<string, string> = {
	// Semantic document QA issue codes.
	answer_leakage: 'Answer leakage',
	factual_inaccuracy: 'Factual inaccuracy',
	misconception_unresolved: 'Misconception left unresolved',
	assessment_duplicates_example: 'Assessment duplicates a worked example',
	progression_gap: 'Progression gap',
	unsupported_claim: 'Unsupported claim',
	metadata_leak: 'Metadata leak',
	// Deterministic QA issue codes that can also surface for review context.
	section_count_mismatch: 'Section count mismatch',
	document_title_mismatch: 'Document title mismatch',
	document_hash_mismatch: 'Document hash mismatch',
	section_order_mismatch: 'Section order mismatch',
	unplanned_section: 'Unplanned section',
	expected_shape_missing: 'Expected content missing',
	required_media_missing: 'Required media missing',
	must_establish_uncovered: 'Required content not established',
	avoid_repeating_violated: 'Repeats content it should avoid',
	bridge_unrealized: 'Transition bridge not realized',
	exit_state_unrealized: 'Section exit state not realized',
	boundary_bridge_missing: 'Missing bridge from the previous section',
	boundary_prerequisite_gap: 'Prerequisite gap at the section boundary',
	boundary_exit_state_missing: 'Missing section exit state',
	boundary_repetition: 'Unwanted repetition across sections'
};

/** Map a QA issue code to a human-readable label; unknown codes fall back to the code. */
export function issueLabel(code: string): string {
	return ISSUE_LABELS[code] ?? code;
}

function displayOf<T>(node: SharedNode): T {
	return (node.display ?? {}) as T;
}

/** Enumerate every reviewer-editable field on a document, in document order. */
export function editableFieldsForDocument(document: SharedLessonDocument): EditableField[] {
	const fields: EditableField[] = [];
	const tasksById = new Map((document.tasks ?? []).map((task) => [task.id, task]));
	for (const section of document.sections) {
		for (const node of section.nodes) {
			if (node.kind === 'paragraph' || node.kind === 'heading') {
				const display = displayOf<SharedParagraphDisplay>(node);
				fields.push({
					key: fieldKey({ section_id: section.id, node_id: node.id, field: 'text' }),
					section_id: section.id,
					node_id: node.id,
					node_kind: node.kind,
					field: 'text',
					label: node.kind === 'heading' ? 'Heading text' : 'Paragraph text',
					value: display.text ?? ''
				});
				fields.push({
					key: fieldKey({
						section_id: section.id,
						node_id: node.id,
						field: 'accessibility_description'
					}),
					section_id: section.id,
					node_id: node.id,
					node_kind: node.kind,
					field: 'accessibility_description',
					label: 'Accessibility description',
					value: node.accessibility?.description ?? ''
				});
			} else if (node.kind === 'callout') {
				const display = displayOf<SharedCalloutDisplay>(node);
				fields.push({
					key: fieldKey({ section_id: section.id, node_id: node.id, field: 'callout_title' }),
					section_id: section.id,
					node_id: node.id,
					node_kind: node.kind,
					field: 'callout_title',
					label: 'Callout title',
					value: display.title ?? ''
				});
				fields.push({
					key: fieldKey({ section_id: section.id, node_id: node.id, field: 'callout_body' }),
					section_id: section.id,
					node_id: node.id,
					node_kind: node.kind,
					field: 'callout_body',
					label: 'Callout body',
					value: display.body ?? ''
				});
				fields.push({
					key: fieldKey({
						section_id: section.id,
						node_id: node.id,
						field: 'accessibility_description'
					}),
					section_id: section.id,
					node_id: node.id,
					node_kind: node.kind,
					field: 'accessibility_description',
					label: 'Accessibility description',
					value: node.accessibility?.description ?? ''
				});
			} else if (node.kind === 'figure') {
				const display = displayOf<SharedFigureDisplay>(node);
				fields.push({
					key: fieldKey({ section_id: section.id, node_id: node.id, field: 'figure_caption' }),
					section_id: section.id,
					node_id: node.id,
					node_kind: node.kind,
					field: 'figure_caption',
					label: 'Figure caption',
					value: display.caption ?? ''
				});
				fields.push({
					key: fieldKey({ section_id: section.id, node_id: node.id, field: 'figure_alt_text' }),
					section_id: section.id,
					node_id: node.id,
					node_kind: node.kind,
					field: 'figure_alt_text',
					label: 'Figure alt text',
					value: node.accessibility?.alt_text ?? ''
				});
			} else if (node.kind === 'list') {
				const display = displayOf<SharedListDisplay>(node);
				(display.items ?? []).forEach((item, index) => {
					fields.push({
						key: fieldKey({
							section_id: section.id,
							node_id: node.id,
							field: 'list_item_text',
							item_index: index
						}),
						section_id: section.id,
						node_id: node.id,
						node_kind: node.kind,
						field: 'list_item_text',
						item_index: index,
						label: `List item ${index + 1}`,
						value: item
					});
				});
				fields.push({
					key: fieldKey({
						section_id: section.id,
						node_id: node.id,
						field: 'accessibility_description'
					}),
					section_id: section.id,
					node_id: node.id,
					node_kind: node.kind,
					field: 'accessibility_description',
					label: 'Accessibility description',
					value: node.accessibility?.description ?? ''
				});
			} else if (node.kind === 'table') {
				const display = displayOf<SharedTableDisplay>(node);
				(display.rows ?? []).forEach((row, rowIndex) => {
					row.forEach((cell, columnIndex) => {
						fields.push({
							key: fieldKey({
								section_id: section.id,
								node_id: node.id,
								field: 'table_cell_text',
								row_index: rowIndex,
								column_index: columnIndex
							}),
							section_id: section.id,
							node_id: node.id,
							node_kind: node.kind,
							field: 'table_cell_text',
							row_index: rowIndex,
							column_index: columnIndex,
							label: `Row ${rowIndex + 1}, column ${columnIndex + 1}`,
							value: cell
						});
					});
				});
				fields.push({
					key: fieldKey({
						section_id: section.id,
						node_id: node.id,
						field: 'accessibility_description'
					}),
					section_id: section.id,
					node_id: node.id,
					node_kind: node.kind,
					field: 'accessibility_description',
					label: 'Accessibility description',
					value: node.accessibility?.description ?? ''
				});
			}
			if (node.kind === 'task_anchor' && node.task_spec_id) {
				// Only the task's wording is editable; its answer key stays locked.
				const task = tasksById.get(node.task_spec_id);
				if (task) fields.push(...editableTaskFields(section.id, node, task));
			}
		}
	}
	return fields;
}

/**
 * Build the minimal set of allowlisted edits to submit, given the document's
 * editable fields at last save and the reviewer's current form values.
 *
 * Only fields whose value actually changed are included, and blank values are
 * dropped (the backend requires a non-empty value for every edit).
 */
export function buildReviewDraftEdits(
	baselineFields: EditableField[],
	currentValues: ReadonlyMap<string, string>
): ReviewDraftTextEdit[] {
	const edits: ReviewDraftTextEdit[] = [];
	for (const field of baselineFields) {
		const next = currentValues.get(field.key);
		if (next === undefined || next === field.value || next.trim() === '') continue;
		edits.push({
			section_id: field.section_id,
			node_id: field.node_id,
			field: field.field,
			value: next,
			item_index: field.item_index,
			row_index: field.row_index,
			column_index: field.column_index,
			option_id: field.option_id,
			feedback_key: field.feedback_key
		});
	}
	return edits;
}

/** Section ids named by at least one QA issue. */
export function issueSectionIds(issues: ContinuityIssue[]): Set<string> {
	return new Set(issues.map((issue) => issue.affected_section_id));
}

/** Node ids named by at least one QA issue, across all sections. */
export function issueNodeIds(issues: ContinuityIssue[]): Set<string> {
	const ids = new Set<string>();
	for (const issue of issues) {
		for (const nodeId of issue.affected_node_ids) ids.add(nodeId);
	}
	return ids;
}
