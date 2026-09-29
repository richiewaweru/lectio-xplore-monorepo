import { describe, expect, it } from 'vitest';

import {
	applyProgressRefreshWhileEditing,
	conflictFrom409,
	isEditorDirty,
	resolveConflict
} from '$lib/curriculum/units/edit-protection';
import { createLearnPathJobState } from '$lib/learn/jobs/path-job-state';
import { createPrintPathJobState } from '$lib/print/jobs/path-job-state';
import { anyPathJobBusy, emptyBusyMap } from '$lib/reliability/operation-lanes';
import type { ArtifactWorkspaceStatus } from '$lib/types/units';

function ws(overrides: Partial<ArtifactWorkspaceStatus> = {}): ArtifactWorkspaceStatus {
	return { state: 'running', realization_id: 'r1', run_id: 'run-1', ...overrides };
}

describe('P05 independent path jobs (G19/G20)', () => {
	it('allows Print and Learn jobs to run without sharing a single busy flag', () => {
		const printJob = createPrintPathJobState();
		const learnJob = createLearnPathJobState();
		const busy = emptyBusyMap();

		expect(printJob.begin('Generating Print…')).toBe(true);
		expect(learnJob.begin('Generating Learn…')).toBe(true);
		expect(printJob.busyLabel).toBe('Generating Print…');
		expect(learnJob.busyLabel).toBe('Generating Learn…');

		const dual = { ...busy, print: printJob.busyLabel, learn: learnJob.busyLabel };
		expect(anyPathJobBusy(dual)).toBe(true);
		expect(dual.plan).toBeNull();
		expect(dual.save).toBeNull();

		// Learn remains busy while Print completes — no shared corruption.
		printJob.end();
		expect(printJob.busyLabel).toBeNull();
		expect(learnJob.busyLabel).toBe('Generating Learn…');
		expect(learnJob.canPrepare(true, false)).toBe(false);
	});

	it('gates prepare on the lesson-status workspace state', () => {
		const printJob = createPrintPathJobState();
		expect(printJob.canPrepare(true, false)).toBe(true);
		printJob.applyWorkspace(ws({ state: 'running' }));
		expect(printJob.canPrepare(true, false)).toBe(false);
		printJob.applyWorkspace(ws({ state: 'needs_review' }));
		expect(printJob.canPrepare(true, false)).toBe(false);
		printJob.applyWorkspace(ws({ state: 'failed_recoverable' }));
		expect(printJob.canPrepare(true, false)).toBe(true);
		expect(printJob.canPrepare(false, false)).toBe(false);
		expect(printJob.canPrepare(true, true)).toBe(false);
	});

	it('maps every workspace state to a phase and action', () => {
		const learnJob = createLearnPathJobState();
		const cases: Array<[Partial<ArtifactWorkspaceStatus>, string, string]> = [
			[{ state: 'not_created' }, 'not_created', 'none'],
			[{ state: 'queued' }, 'in_progress', 'wait'],
			[{ state: 'running' }, 'in_progress', 'wait'],
			[{ state: 'needs_review' }, 'needs_review', 'review'],
			[{ state: 'failed_recoverable', recovery_action: 'retry' }, 'failed_recoverable', 'retry'],
			[{ state: 'failed_terminal', recovery_action: 'regenerate' }, 'failed_terminal', 'regenerate'],
			[{ state: 'failed_terminal', recovery_action: 'none' }, 'failed_terminal', 'regenerate'],
			[{ state: 'ready' }, 'ready', 'open']
		];
		for (const [overrides, phase, action] of cases) {
			learnJob.applyWorkspace(ws(overrides));
			expect(learnJob.job.phase).toBe(phase);
			expect(learnJob.job.action).toBe(action);
		}
	});

	it('carries run_id, recovery_action, and error from the DTO; legacy rows regenerate', () => {
		const printJob = createPrintPathJobState();
		printJob.applyWorkspace(
			ws({
				state: 'failed_terminal',
				recovery_action: 'regenerate',
				error: { message: 'Created before the job update - regenerate this output.' }
			})
		);
		expect(printJob.job).toEqual({
			phase: 'failed_terminal',
			action: 'regenerate',
			recoveryAction: 'regenerate',
			runId: 'run-1',
			errorMessage: 'Created before the job update - regenerate this output.'
		});
		printJob.applyWorkspace(null);
		expect(printJob.job.phase).toBe('not_created');
	});
});

describe('P05 dirty preservation and 409 (G21)', () => {
	it('preserves dirty draft across progress refresh', () => {
		const draft = {
			title: 'Local title',
			objective: 'Local objective',
			must_establish: 'a',
			exclusions: ''
		};
		const result = applyProgressRefreshWhileEditing({
			dirty: true,
			draft,
			incoming: {
				title: 'Server title',
				objective: 'Server objective',
				must_establish: 'b',
				exclusions: '',
				revision: 9
			}
		});
		expect(result.preserved).toBe(true);
		expect(result.draft.title).toBe('Local title');
		expect(isEditorDirty(draft, {
			title: 'Server title',
			objective: 'Server objective',
			must_establish: 'b',
			exclusions: ''
		})).toBe(true);
	});

	it('keeps local edits on 409 and supports reload/resolve', () => {
		const draft = {
			title: 'Tab A edit',
			objective: 'Keep me',
			must_establish: 'x',
			exclusions: ''
		};
		const conflict = conflictFrom409({
			message: 'Path revision conflict',
			draft,
			localRevision: 3,
			serverRevision: 4
		});
		expect(conflict.local_draft.title).toBe('Tab A edit');

		const keep = resolveConflict(conflict, 'keep_editing', null);
		expect(keep.draft.title).toBe('Tab A edit');
		expect(keep.conflict).toBeNull();

		const reload = resolveConflict(conflict, 'reload_server', {
			title: 'Server title',
			objective: 'Server objective',
			must_establish: 'y',
			exclusions: '',
			revision: 4
		});
		expect(reload.draft.title).toBe('Server title');
		expect(reload.baseline?.title).toBe('Server title');
	});
});
