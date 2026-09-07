export interface GenerationPoller {
	isRunning(): boolean;
	start(options?: { immediate?: boolean }): void;
	stop(): void;
}

interface VisibilityTarget {
	readonly hidden: boolean;
	addEventListener(type: 'visibilitychange', listener: () => void): void;
	removeEventListener(type: 'visibilitychange', listener: () => void): void;
}

export function createGenerationPoller(
	poll: () => Promise<void>,
	{
		intervalMs = 4000,
		visibilityTarget = typeof document === 'undefined' ? null : document
	}: { intervalMs?: number; visibilityTarget?: VisibilityTarget | null } = {}
): GenerationPoller {
	let interval: ReturnType<typeof setInterval> | null = null;
	let inFlight = false;

	async function run(): Promise<void> {
		if (visibilityTarget?.hidden || inFlight) return;
		inFlight = true;
		try {
			await poll();
		} catch {
			// Polling is opportunistic; the next interval retries the current snapshot.
		} finally {
			inFlight = false;
		}
	}

	function handleVisibilityChange(): void {
		if (!visibilityTarget?.hidden) void run();
	}

	function stop(): void {
		if (interval) clearInterval(interval);
		interval = null;
		visibilityTarget?.removeEventListener('visibilitychange', handleVisibilityChange);
	}

	return {
		isRunning: () => interval !== null,
		start({ immediate = true } = {}) {
			if (interval) return;
			visibilityTarget?.addEventListener('visibilitychange', handleVisibilityChange);
			if (immediate) void run();
			interval = setInterval(() => void run(), intervalMs);
		},
		stop
	};
}
