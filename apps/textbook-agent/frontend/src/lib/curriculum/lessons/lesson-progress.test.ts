import { describe, expect, it } from 'vitest';
import { formatElapsed, progressView } from './lesson-progress';

describe('progressView', () => {
	it('returns null without steps', () => {
		expect(progressView(null)).toBeNull();
		expect(progressView({ steps: [] })).toBeNull();
	});

	it('derives counts, markers and start time', () => {
		const view = progressView({
			steps: [
				{ key: 'sourcebook', label: 'Gathering source notes', status: 'done' },
				{ key: 'write', label: 'Writing sections', status: 'active', done: 2, total: 5 }
			],
			current_label: 'Writing sections (2/5)',
			started_at: '2026-10-01T12:00:00Z'
		});
		expect(view?.steps.map((s) => s.counts)).toEqual(['', '(2/5)']);
		expect(view?.steps.map((s) => s.marker)).toEqual(['done', 'active']);
		expect(view?.currentLabel).toBe('Writing sections (2/5)');
		expect(view?.startedAt).toBe(Date.parse('2026-10-01T12:00:00Z'));
	});
});

describe('formatElapsed', () => {
	it('formats seconds and minutes, clamps skew', () => {
		const start = 1_000_000;
		expect(formatElapsed(null, start)).toBeNull();
		expect(formatElapsed(start, start - 5000)).toBe('0s');
		expect(formatElapsed(start, start + 42_000)).toBe('42s');
		expect(formatElapsed(start, start + 125_000)).toBe('2m 05s');
	});
});
