import { afterEach, describe, expect, it, vi } from 'vitest';

import { createGenerationPoller } from './generation-poller';

function visibilityTarget() {
	let listener: (() => void) | null = null;
	return {
		hidden: false,
		addEventListener: vi.fn((_type: 'visibilitychange', next: () => void) => {
			listener = next;
		}),
		removeEventListener: vi.fn(() => {
			listener = null;
		}),
		show() {
			this.hidden = false;
			listener?.();
		}
	};
}

afterEach(() => vi.useRealTimers());

describe('createGenerationPoller', () => {
	it('runs one interval, prevents overlap, and stops cleanly', async () => {
		vi.useFakeTimers();
		let release!: () => void;
		const poll = vi.fn(
			() =>
				new Promise<void>((resolve) => {
					release = resolve;
				})
		);
		const target = visibilityTarget();
		const poller = createGenerationPoller(poll, { intervalMs: 1000, visibilityTarget: target });

		poller.start();
		poller.start();
		expect(poll).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(2000);
		expect(poll).toHaveBeenCalledTimes(1);
		release();
		await Promise.resolve();
		await vi.advanceTimersByTimeAsync(1000);
		expect(poll).toHaveBeenCalledTimes(2);

		poller.stop();
		release();
		await vi.advanceTimersByTimeAsync(2000);
		expect(poll).toHaveBeenCalledTimes(2);
		expect(target.removeEventListener).toHaveBeenCalledTimes(1);
	});

	it('polls immediately when a hidden document becomes visible', async () => {
		vi.useFakeTimers();
		const poll = vi.fn(async () => undefined);
		const target = visibilityTarget();
		target.hidden = true;
		const poller = createGenerationPoller(poll, { visibilityTarget: target });
		poller.start();
		expect(poll).not.toHaveBeenCalled();
		target.show();
		await Promise.resolve();
		expect(poll).toHaveBeenCalledTimes(1);
		poller.stop();
	});
});
