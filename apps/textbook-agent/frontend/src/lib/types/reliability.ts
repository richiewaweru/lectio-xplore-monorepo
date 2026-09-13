/**
 * Frontend contracts for reliability progress (P04 status/events).
 * Aligned with `/api/v1/realizations/{id}/status|events`.
 */

export type ReliabilityPathKind = 'print' | 'learn' | 'plan' | 'unit';

export type ReliabilityRunPhase =
	| 'queued'
	| 'running'
	| 'waiting'
	| 'succeeded'
	| 'failed'
	| 'cancelled'
	| 'ready'
	| 'failed_recoverable'
	| 'failed_terminal'
	| 'stale'
	| 'read_only'
	| string;

export type ReliabilityAllowedAction =
	| 'refresh'
	| 'retry'
	| 'resume'
	| 'cancel'
	| 'regenerate'
	| 'prepare_print'
	| 'prepare_learn'
	| 'save'
	| 'plan'
	| 'approve'
	| 'reload'
	| 'open'
	| string;

export interface ReliabilityActiveItem {
	item_id: string;
	stage: string;
	attempt: number;
	state?: string;
}

export interface ReliabilityRunStatus {
	run_id: string;
	owner_id: string;
	path: ReliabilityPathKind | string;
	stage: string;
	status: ReliabilityRunPhase;
	active_items: ReliabilityActiveItem[];
	completed_count: number | null;
	total_count: number | null;
	next_retry_at: string | null;
	allowed_actions: ReliabilityAllowedAction[];
	document_revision: number | null;
	path_revision: number | null;
	last_sequence: number;
}

export interface ReliabilityProgressEvent {
	sequence: number;
	run_id: string;
	owner_id: string;
	path: ReliabilityPathKind | string;
	stage: string;
	item_id: string | null;
	attempt: number | null;
	event_type: string;
	occurred_at: string;
	error_category: string | null;
	message: string | null;
}

export interface ReliabilityConflictState {
	message: string;
	local_revision: number | null;
	server_revision: number | null;
	/** Local editor draft preserved across the conflict. */
	local_draft: {
		title: string;
		objective: string;
		must_establish: string;
		exclusions: string;
	};
}
