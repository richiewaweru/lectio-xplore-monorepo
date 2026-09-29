/** Pure helpers for the SharedLessonDocument reviewer path (no I/O here). */

export type SharedNodeKind =
	| 'paragraph'
	| 'heading'
	| 'list'
	| 'figure'
	| 'table'
	| 'callout'
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
	body: string;
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
		| SharedCalloutDisplay;
	accessibility?: SharedNodeAccessibility;
}

export interface SharedSection {
	id: string;
	title: string;
	position: number;
	nodes: SharedNode[];
}

export interface SharedLessonDocument {
	schema_version: number;
	id: string;
	revision: number;
	content_hash: string;
	title: string;
	sections: SharedSection[];
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
	| 'accessibility_description';

export interface ReviewDraftTextEdit {
	section_id: string;
	node_id: string;
	field: ReviewEditField;
	value: string;
	item_index?: number;
	row_index?: number;
	column_index?: number;
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
}

export function fieldKey(target: EditableFieldTarget): string {
	return [
		target.section_id,
		target.node_id,
		target.field,
		target.item_index ?? '',
		target.row_index ?? '',
		target.column_index ?? ''
	].join('::');
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
			// task_anchor nodes are frozen from the plan and carry no editable field.
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
			column_index: field.column_index
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
