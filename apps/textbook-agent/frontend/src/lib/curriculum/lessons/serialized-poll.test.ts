import { afterEach, describe, expect, it, vi } from 'vitest';
import { createSerializedPoll } from './serialized-poll';

afterEach(() => vi.useRealTimers());

describe('createSerializedPoll', () => {
	it('refreshes queued Learn until ready and never overlaps refreshes', async () => {
		vi.useFakeTimers();
		let state: 'queued' | 'ready' = 'queued';
		let releaseFirst: ((continuePolling: boolean) => void) | undefined;
		const observed: string[] = [];
		const poll = createSerializedPoll(() => {
			observed.push(state);
			if (observed.length === 1) {
				return new Promise<boolean>((resolve) => (releaseFirst = resolve));
			}
			return Promise.resolve(state === 'queued');
		}, 10);

		poll.start();
		await vi.advanceTimersByTimeAsync(10);
		expect(observed).toEqual(['queued']);
		// A refresh that takes longer than the poll interval cannot overlap itself.
		await vi.advanceTimersByTimeAsync(100);
		expect(observed).toEqual(['queued']);
		releaseFirst?.(true);
		await vi.advanceTimersByTimeAsync(0);
		state = 'ready';
		await vi.advanceTimersByTimeAsync(10);
		expect(observed).toEqual(['queued', 'ready']);
		await vi.advanceTimersByTimeAsync(50);
		expect(observed).toEqual(['queued', 'ready']);
	});

	it.each([
		['awaiting teacher review', false],
		['ready', false],
		['recoverable failure', false],
		['terminal failure', false]
	] as const)('stops polling when backend reports %s', async (_state, shouldContinue) => {
		vi.useFakeTimers();
		const work = vi.fn(async () => shouldContinue);
		const poll = createSerializedPoll(work, 10);
		poll.start();
		await vi.advanceTimersByTimeAsync(10);
		expect(work).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(50);
		expect(work).toHaveBeenCalledTimes(1);
	});

	it('restarts after an explicit retry and stops again at the next failure', async () => {
		vi.useFakeTimers();
		const decisions = [false, true, false];
		const work = vi.fn(async () => decisions.shift() ?? false);
		const poll = createSerializedPoll(work, 10);
		poll.start();
		await vi.advanceTimersByTimeAsync(10);
		expect(work).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(50);
		expect(work).toHaveBeenCalledTimes(1);
		poll.start(); // Explicit retry admitted a new queued run.
		await vi.advanceTimersByTimeAsync(10);
		expect(work).toHaveBeenCalledTimes(2);
		await vi.advanceTimersByTimeAsync(10);
		expect(work).toHaveBeenCalledTimes(3);
		await vi.advanceTimersByTimeAsync(50);
		expect(work).toHaveBeenCalledTimes(3);
	});

	it('backs off after the threshold; a second start() adds no second timer', async () => {
		vi.useFakeTimers();
		let calls = 0;
		const poll = createSerializedPoll(
			async () => {
				calls += 1;
				return true;
			},
			2000,
			{ slowAfterMs: 30_000, slowIntervalMs: 5000 }
		);
		poll.start();
		poll.start();
		await vi.advanceTimersByTimeAsync(30_000);
		expect(calls).toBe(15);
		const before = calls;
		await vi.advanceTimersByTimeAsync(30_000);
		expect(calls - before).toBeLessThanOrEqual(7);
		poll.stop();
		const after = calls;
		await vi.advanceTimersByTimeAsync(60_000);
		expect(calls).toBe(after);
	});

	it('skips work while paused (hidden tab) but keeps its timer', async () => {
		vi.useFakeTimers();
		let paused = true;
		let calls = 0;
		const poll = createSerializedPoll(
			async () => {
				calls += 1;
				return true;
			},
			1000,
			{ pauseWhen: () => paused }
		);
		poll.start();
		await vi.advanceTimersByTimeAsync(5000);
		expect(calls).toBe(0);
		paused = false;
		await vi.advanceTimersByTimeAsync(1000);
		expect(calls).toBe(1);
		poll.stop();
	});

	it('restarts after stop while a run is in flight', async () => {
		vi.useFakeTimers();
		let release: (() => void) | undefined;
		let calls = 0;
		const poll = createSerializedPoll(() => {
			calls += 1;
			return new Promise<boolean>((resolve) => (release = () => resolve(true)));
		}, 10);
		poll.start();
		await vi.advanceTimersByTimeAsync(10);
		poll.stop();
		poll.start();
		release?.();
		await vi.advanceTimersByTimeAsync(10);
		expect(calls).toBe(2);
		poll.stop();
	});
});
