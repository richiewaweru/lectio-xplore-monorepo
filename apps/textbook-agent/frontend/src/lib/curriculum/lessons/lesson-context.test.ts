import { describe, expect, it } from 'vitest';
import type { PreparedLessonStatus } from '$lib/types/units';
import { lessonArtifactUi, resolvePrintGenerationId } from './lesson-context';

const base = (overrides: Partial<PreparedLessonStatus> = {}): PreparedLessonStatus => ({
	path_lesson_id: 'lesson-1', lesson_revision: 1, generation_id: 'prep-1',
	generation_status: 'complete', workflow_stage: 'complete', objective_hash: 'hash',
	stale: false, can_prepare: false, can_regenerate: true, realizations: [], ...overrides
});

describe('lessonArtifactUi', () => {
	it('does not infer Print from preparation generation', () => {
		const status = base();
		expect(resolvePrintGenerationId(status)).toBeNull();
		expect(lessonArtifactUi(status, 'print').state).toBe('not_created');
	});

	it('recognizes each path independently', () => {
		const status = base({
			learn_realization_id: 'learn-r', learn_output_id: 'learn-o',
			realizations: [{ path: 'learn', realization_id: 'learn-r', output_id: 'learn-o', status: 'ready' } as never]
		});
		expect(lessonArtifactUi(status, 'learn')).toMatchObject({ exists: true, state: 'ready', outputId: 'learn-o' });
		expect(lessonArtifactUi(status, 'print')).toMatchObject({ exists: false, state: 'not_created' });
	});

	it('reports a realization with no output as preparing', () => {
		const status = base({ realizations: [{ path: 'print', realization_id: 'print-r', output_id: null, status: 'queued' } as never] });
		expect(lessonArtifactUi(status, 'print')).toMatchObject({ exists: true, state: 'preparing', realizationId: 'print-r' });
	});

	it('keeps failed and stale identity visible', () => {
		const failed = base({ realizations: [{ path: 'learn', realization_id: 'r', output_id: 'o', status: 'failed_terminal', error_summary: 'bad document' } as never] });
		expect(lessonArtifactUi(failed, 'learn')).toMatchObject({ exists: true, state: 'failed', outputId: 'o' });
		const stale = base({ stale: true, print_output_id: 'old-print' });
		expect(lessonArtifactUi(stale, 'print')).toMatchObject({ exists: true, state: 'needs_attention' });
	});

	it('preserves existence when document loading fails', () => {
		const status = base({ learn_output_id: 'learn-o' });
		expect(lessonArtifactUi(status, 'learn', 'preview unavailable')).toMatchObject({ exists: true, state: 'needs_attention', errorSummary: 'preview unavailable' });
	});
});
