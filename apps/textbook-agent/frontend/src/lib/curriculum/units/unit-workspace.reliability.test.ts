import { describe, expect, it, vi } from 'vitest';

import {
	createManagedReliabilitySubscription,
	createScopedEventSink,
	reliabilityEventsPath,
	reliabilityStatusPath
} from '$lib/api/reliability';
import {
	applyProgressRefreshWhileEditing,
	conflictFrom409,
	isEditorDirty,
	resolveConflict
} from '$lib/curriculum/units/edit-protection';
import { createLearnPathJobState } from '$lib/learn/jobs/path-job-state';
import { createPrintPathJobState } from '$lib/print/jobs/path-job-state';
import { anyPathJobBusy, emptyBusyMap } from '$lib/reliability/operation-lanes';
import type { ReliabilityProgressEvent, ReliabilityRunStatus } from '$lib/types/reliability';

function event(
	overrides: Partial<ReliabilityProgressEvent> & Pick<ReliabilityProgressEvent, 'sequence'>
): ReliabilityProgressEvent {
	return {
		run_id: 'run-1',
		owner_id: 'unit-1',
		path: 'print',
		stage: 'generate',
		item_id: null,
		attempt: 1,
		event_type: 'progress',
		occurred_at: '2026-09-13T00:00:00Z',
		error_category: null,
		message: null,
		...overrides
	};
}

function status(overrides: Partial<ReliabilityRunStatus> = {}): ReliabilityRunStatus {
	return {
		run_id: 'run-1',
		owner_id: 'unit-1',
		path: 'print',
		stage: 'generate',
		status: 'running',
		active_items: [],
		completed_count: 1,
		total_count: 3,
		next_retry_at: null,
		allowed_actions: ['prepare_print', 'save'],
		document_revision: 2,
		path_revision: 4,
		last_sequence: 2,
		...overrides
	};
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

	it('derives prepare availability from server allowed_actions', () => {
		const printJob = createPrintPathJobState();
		printJob.applyStatus(status({ allowed_actions: ['prepare_learn'] }));
		expect(printJob.canPrepare(true, false)).toBe(false);

		printJob.applyStatus(status({ allowed_actions: ['prepare_print'] }));
		expect(printJob.canPrepare(true, false)).toBe(true);
	});
});

describe('P05 scoped subscriptions (G20)', () => {
	it('ignores stale, wrong-owner, and disposed events', () => {
		const sink = createScopedEventSink('unit-1', 'run-1', 2);
		expect(sink.accept(event({ sequence: 2 }))).toBeNull();
		expect(sink.accept(event({ sequence: 3, owner_id: 'other' }))).toBeNull();
		expect(sink.accept(event({ sequence: 3, run_id: 'run-2' }))).toBeNull();
		expect(sink.accept(event({ sequence: 3 }))?.sequence).toBe(3);
		expect(sink.accept(event({ sequence: 3 }))).toBeNull();
		sink.dispose();
		expect(sink.accept(event({ sequence: 4 }))).toBeNull();
	});

	it('unsubscribes on dispose and does not duplicate listeners on reconnect', () => {
		const unsubs: Array<() => void> = [];
		const subscribe = vi.fn(
			(opts: {
				ownerId: string;
				runId: string;
				afterSequence?: number;
				handlers: { onEvent?: (e: ReliabilityProgressEvent) => void };
			}) => {
				const unsub = vi.fn();
				unsubs.push(unsub);
				// expose handler for reconnect proof
				(subscribe as unknown as { lastHandlers: typeof opts.handlers }).lastHandlers =
					opts.handlers;
				return unsub;
			}
		);

		const managed = createManagedReliabilitySubscription(
			'unit-1',
			'run-1',
			{
				onEvent: vi.fn()
			},
			{ subscribe: subscribe as never, afterSequence: 0 }
		);

		expect(subscribe).toHaveBeenCalledTimes(1);
		managed.reconnect(1);
		expect(subscribe).toHaveBeenCalledTimes(2);
		expect(unsubs[0]).toHaveBeenCalledTimes(1);

		managed.dispose();
		expect(unsubs[1]).toHaveBeenCalledTimes(1);
		managed.reconnect(5);
		expect(subscribe).toHaveBeenCalledTimes(2);
	});

	it('builds planned P04 status/events paths', () => {
		expect(reliabilityStatusPath('run-1')).toBe('/api/v1/realizations/run-1/status');
		expect(reliabilityEventsPath('run-1', 7)).toBe(
			'/api/v1/realizations/run-1/events?after_seq=7'
		);
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
