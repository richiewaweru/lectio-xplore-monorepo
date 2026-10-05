import { describe, expect, it } from 'vitest';
import { autoRetryText, formatElapsed, parseUtc, progressView } from './lesson-progress';

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

describe('started_at robustness', () => {
	const steps = [{ key: 'a', label: 'A', status: 'active' as const }];

	it('treats a +00:00 timestamp from now-10s as under a minute', () => {
		const iso = new Date(Date.now() - 10_000).toISOString().replace('Z', '+00:00');
		const view = progressView({ steps, started_at: iso });
		expect(formatElapsed(view!.startedAt, Date.now())).toMatch(/^\d+s$/);
	});

	it('treats an offset-less timestamp as UTC', () => {
		expect(parseUtc('2026-10-01T12:00:00')).toBe(Date.parse('2026-10-01T12:00:00Z'));
		expect(parseUtc('2026-10-01 12:00:00.5')).toBe(Date.parse('2026-10-01T12:00:00.5Z'));
		expect(parseUtc('2026-10-01T12:00:00+02:00')).toBe(Date.parse('2026-10-01T10:00:00Z'));
		const iso = new Date(Date.now() - 10_000).toISOString().replace('Z', '');
		const view = progressView({ steps, started_at: iso });
		expect(formatElapsed(view!.startedAt, Date.now())).toMatch(/^\d+s$/);
	});
});

describe('figures and auto-retry', () => {
	it('builds the figures line, failed figures and warnings', () => {
		const view = progressView({
			steps: [{ key: 'media', label: 'Figures: 2 ready / 1 failed / 5 planned', status: 'active' }],
			figures_planned: 5, figures_ready: 2, figures_failed: 1,
			figures: [
				{ figure_id: 'f1', section_title: 'Evaporation', status: 'failed', error_summary: 'Image service timed out.', retryable: true },
				{ figure_id: 'f2', status: 'ready', warnings: ["'evaporation' not found in text"] }
			]
		});
		expect(view?.figuresLine).toBe('Figures: 2 ready / 1 failed / 5 planned');
		expect(view?.failedFigures).toEqual([{ id: 'f1', sectionTitle: 'Evaporation', summary: 'Image service timed out.', retryable: true }]);
		expect(view?.labelWarnings).toEqual(["'evaporation' not found in text"]);
	});

	it('formats auto-retry text', () => {
		expect(autoRetryText(null)).toBeNull();
		expect(autoRetryText({ attempt: 2, maxAttempts: 3 })).toBe('Retrying automatically (attempt 2 of 3).');
	});
});
