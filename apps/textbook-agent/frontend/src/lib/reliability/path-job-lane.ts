/**
 * Shared path-job lane contract. Print/Learn implement this; Unit composes it
 * without importing sibling domain modules.
 *
 * Job state is derived only from the lesson-status DTO (`workspace.learn` /
 * `workspace.print`), which the backend projects from generation Runs. There is
 * no separate progress/status endpoint.
 */

import type { ArtifactWorkspaceStatus } from '$lib/types/units';

export type PathJobPhase =
	| 'not_created'
	| 'in_progress'
	| 'needs_review'
	| 'failed_recoverable'
	| 'failed_terminal'
	| 'ready';

/** What the UI should offer. `regenerate` and `retry` both use the realization retry route. */
export type PathJobAction = 'none' | 'wait' | 'review' | 'retry' | 'regenerate' | 'open';

export interface PathJobDerived {
	phase: PathJobPhase;
	action: PathJobAction;
	recoveryAction: string | null;
	runId: string | null;
	errorMessage: string | null;
}

export const EMPTY_PATH_JOB: PathJobDerived = {
	phase: 'not_created',
	action: 'none',
	recoveryAction: null,
	runId: null,
	errorMessage: null
};

export function derivePathJob(workspace: ArtifactWorkspaceStatus | null | undefined): PathJobDerived {
	if (!workspace) return EMPTY_PATH_JOB;
	const recoveryAction = workspace.recovery_action ?? workspace.error?.recovery_action ?? null;
	const base = {
		recoveryAction,
		runId: workspace.run_id ?? null,
		errorMessage: workspace.error?.message ?? null
	};
	switch (workspace.state) {
		case 'queued':
		case 'running':
			return { ...base, phase: 'in_progress', action: 'wait' };
		case 'needs_review':
			return { ...base, phase: 'needs_review', action: 'review' };
		case 'ready':
			return { ...base, phase: 'ready', action: 'open' };
		case 'failed_recoverable':
			return {
				...base,
				phase: 'failed_recoverable',
				action: recoveryAction === 'regenerate' ? 'regenerate' : 'retry'
			};
		case 'failed_terminal':
			return { ...base, phase: 'failed_terminal', action: 'regenerate' };
		default:
			return { ...base, phase: 'not_created', action: 'none' };
	}
}

export interface PathJobLane {
	readonly busyLabel: string | null;
	readonly job: PathJobDerived;
	begin(label?: string): boolean;
	end(): void;
	applyWorkspace(workspace: ArtifactWorkspaceStatus | null | undefined): void;
	canPrepare(pathApproved: boolean, lessonSkipped: boolean): boolean;
}

export function createPathJobLane(defaultLabel: string): PathJobLane {
	let busyLabel: string | null = null;
	let job: PathJobDerived = EMPTY_PATH_JOB;

	return {
		get busyLabel() {
			return busyLabel;
		},
		get job() {
			return job;
		},
		begin(label = defaultLabel) {
			if (busyLabel !== null) return false;
			busyLabel = label;
			return true;
		},
		end() {
			busyLabel = null;
		},
		applyWorkspace(workspace) {
			job = derivePathJob(workspace);
		},
		canPrepare(pathApproved, lessonSkipped) {
			if (busyLabel !== null) return false;
			if (!pathApproved || lessonSkipped) return false;
			return job.phase !== 'in_progress' && job.phase !== 'needs_review';
		}
	};
}
