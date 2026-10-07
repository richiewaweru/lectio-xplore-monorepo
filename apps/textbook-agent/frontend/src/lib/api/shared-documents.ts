import { apiFetch } from '$lib/api/client';
import { ensureOk } from '$lib/api/errors';
import type {
	ContinuityIssue,
	ReviewDraftTextEdit,
	SharedLessonDocument
} from '$lib/curriculum/lessons/review-draft';

const jsonHeaders = { 'Content-Type': 'application/json' };

export interface ReviewDraftIdentity {
	id: string;
	revision: number;
	hash: string;
}

export interface ReviewDraftResponse {
	status: string;
	draft: ReviewDraftIdentity;
	document: SharedLessonDocument;
	issues: ContinuityIssue[];
}

export interface ReviewSubmitResult {
	run_id: string;
	document_id: string;
	document_revision: number;
	work_item_id: string;
	[key: string]: unknown;
}

async function jsonRequest<T>(path: string, fallback: string, init?: RequestInit): Promise<T> {
	const response = await apiFetch(path, init);
	await ensureOk(response, fallback);
	return response.json() as Promise<T>;
}

/** Load the current reviewer draft (document, issues, and revision identity) for a Run. */
export function getReviewDraft(runId: string): Promise<ReviewDraftResponse> {
	return jsonRequest(
		`/api/v1/shared-documents/runs/${encodeURIComponent(runId)}/review-draft`,
		'Could not load the review draft.'
	);
}

/**
 * Save one immutable revision of allowlisted text edits. Fails with a 409
 * ApiError if `expectedRevision`/`expectedHash` no longer match the latest
 * saved draft (someone or something else changed it first).
 */
export function saveReviewDraftRevision(
	runId: string,
	body: { expected_revision: number; expected_hash: string; edits: ReviewDraftTextEdit[] }
): Promise<ReviewDraftResponse> {
	return jsonRequest(
		`/api/v1/shared-documents/runs/${encodeURIComponent(runId)}/review-draft/revisions`,
		'Could not save the review draft.',
		{ method: 'POST', headers: jsonHeaders, body: JSON.stringify(body) }
	);
}

/**
 * Submit the latest saved draft for re-qualification. On success this admits
 * a document QA replacement Run; poll lesson status to learn the outcome
 * (ready, needs_review again, or failed).
 */
export function submitReviewDraft(
	runId: string,
	body: { expected_revision: number; expected_hash: string }
): Promise<ReviewSubmitResult> {
	return jsonRequest(
		`/api/v1/shared-documents/runs/${encodeURIComponent(runId)}/review-draft/submit`,
		'Could not submit the review draft.',
		{ method: 'POST', headers: jsonHeaders, body: JSON.stringify(body) }
	);
}

export interface RegenerateDocumentResult {
	status: string;
	replaced_run_id: string;
	run_id: string;
	path_lesson_id: string;
}

/**
 * Replace a flagged or failed lesson document with a fresh generation attempt.
 * For defects that editing wording cannot fix (e.g. a task whose answer key is
 * wrong). Fails with a 409 ApiError when the document is still generating or
 * its attempts are used up.
 */
export function regenerateSharedDocument(runId: string): Promise<RegenerateDocumentResult> {
	return jsonRequest(
		`/api/v1/shared-documents/runs/${encodeURIComponent(runId)}/regenerate`,
		'Could not regenerate the lesson document.',
		{ method: 'POST' }
	);
}

export interface QualityFlag {
	code: string;
	severity: 'warning';
	source: 'semantic_qa' | 'deterministic_qa' | 'writer_warning' | 'boundary_check';
	message: string;
	section_id: string;
	node_ids: string[];
	required_correction: string;
	previous_section_id?: string;
	next_section_id?: string;
	previous_section_title?: string;
	next_section_title?: string;
	internal_issue_codes?: string[];
}

export interface QualityFlagsResponse {
	run_id: string | null;
	flags: QualityFlag[];
}

/**
 * Non-blocking quality notes recorded by the advisory document quality gate for
 * a Learn lesson (`editableLessonId`) or a Print/Learn output (`generationId`).
 */
export function getQualityFlags(
	target: { editableLessonId: string } | { generationId: string }
): Promise<QualityFlagsResponse> {
	const query =
		'editableLessonId' in target
			? `editable_lesson_id=${encodeURIComponent(target.editableLessonId)}`
			: `generation_id=${encodeURIComponent(target.generationId)}`;
	return jsonRequest(
		`/api/v1/shared-documents/quality-flags?${query}`,
		'Could not load quality notes.'
	);
}
