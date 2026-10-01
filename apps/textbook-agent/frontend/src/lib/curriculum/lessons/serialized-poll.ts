export interface SerializedPollOptions {
	/** After this much polling time, switch to `slowIntervalMs` (gentle backoff). */
	slowAfterMs?: number;
	slowIntervalMs?: number;
	/** Skip the work (but keep the timer) while true, e.g. a hidden tab. */
	pauseWhen?: () => boolean;
	now?: () => number;
}

export function createSerializedPoll(
	work: () => Promise<boolean>,
	intervalMs = 1500,
	options: SerializedPollOptions = {}
): { start: () => void; stop: () => void } {
	const { slowAfterMs, slowIntervalMs, pauseWhen, now = () => Date.now() } = options;
	let timer: ReturnType<typeof setTimeout> | null = null;
	let stopped = true;
	let inFlight = false;
	let startedAt = 0;

	const nextDelay = () =>
		slowAfterMs !== undefined && slowIntervalMs !== undefined && now() - startedAt >= slowAfterMs
			? slowIntervalMs
			: intervalMs;

	const schedule = () => {
		timer = setTimeout(async () => {
			timer = null;
			if (stopped || inFlight) return;
			if (pauseWhen?.()) {
				schedule();
				return;
			}
			inFlight = true;
			try {
				if (!(await work())) stopped = true;
			} catch {
				stopped = true;
			} finally {
				inFlight = false;
				if (!stopped) schedule();
			}
		}, nextDelay());
	};

	return {
		start() {
			if (!stopped) return;
			stopped = false;
			startedAt = now();
			// An in-flight run reschedules itself once it settles.
			if (!inFlight) schedule();
		},
		stop() {
			stopped = true;
			if (timer !== null) clearTimeout(timer);
			timer = null;
		}
	};
}

/** Standard status-poll cadence: 2s for the first 30s, then 5s; idle while the tab is hidden. */
export const LESSON_STATUS_POLL_OPTIONS: SerializedPollOptions = {
	slowAfterMs: 30_000,
	slowIntervalMs: 5_000,
	pauseWhen: () => typeof document !== 'undefined' && document.hidden
};
export const LESSON_STATUS_POLL_MS = 2_000;
