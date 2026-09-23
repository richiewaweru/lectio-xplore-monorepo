export function createSerializedPoll(
	work: () => Promise<boolean>,
	intervalMs = 1500
): { start: () => void; stop: () => void } {
	let timer: ReturnType<typeof setTimeout> | null = null;
	let stopped = true;
	let inFlight = false;

	const schedule = () => {
		timer = setTimeout(async () => {
			timer = null;
			if (stopped || inFlight) return;
			inFlight = true;
			try {
				if (!(await work())) stopped = true;
			} catch {
				stopped = true;
			} finally {
				inFlight = false;
				if (!stopped) schedule();
			}
		}, intervalMs);
	};

	return {
		start() {
			if (!stopped || inFlight) return;
			stopped = false;
			schedule();
		},
		stop() {
			stopped = true;
			if (timer !== null) clearTimeout(timer);
			timer = null;
		}
	};
}
