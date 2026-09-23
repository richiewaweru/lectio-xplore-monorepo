import { describe, expect, it } from 'vitest';
import type { PreparedLessonStatus } from '$lib/types/units';
import {
	canonicalPreparationState,
	lessonArtifactUi,
	preparationIsApprovedAndFresh,
	preparationUiState,
	resolvePlanGenerationId,
	resolvePrintGenerationId
} from './lesson-context';

const base = (overrides: Partial<PreparedLessonStatus> = {}): PreparedLessonStatus => ({
	path_lesson_id: 'lesson-1', lesson_revision: 1, generation_id: 'debug-prep-1',
	generation_status: 'complete', workflow_stage: 'complete', objective_hash: 'hash',
	stale: false, can_prepare: false, can_regenerate: true, realizations: [],
	workspace: {
		preparation: { state: 'not_started' },
		learn: { state: 'not_created' },
		print: { state: 'not_created' }
	},
	...overrides
});

describe('canonical Unit lesson workspace mapping', () => {
	it.each([
		['not_started', 'not_prepared'],
		['planning', 'preparing'],
		['awaiting_review', 'awaiting_review'],
		['approved', 'needs_attention'], // approval requires verified immutable identity
		['failed_recoverable', 'needs_attention'],
		['failed_terminal', 'needs_attention']
	] as const)('maps canonical preparation %s', (state, uiState) => {
		const status = base({
			workflow_stage: 'ready', generation_status: 'ready',
			workspace: {
				preparation: { state, approved_snapshot_verified: state === 'approved' ? false : undefined },
				learn: { state: 'not_created' }, print: { state: 'not_created' }
			}
		});
		expect(canonicalPreparationState(status)).toBe(state);
		expect(preparationUiState(status)).toBe(uiState);
	});

	it('keeps verified approval despite contradictory failed worker fields and downstream failures', () => {
		const status = base({
			generation_status: 'failed', workflow_stage: 'failed_terminal',
			workspace: {
				preparation: { state: 'approved', approved_snapshot_verified: true },
				learn: { state: 'failed_recoverable', realization_id: 'learn-r', error: { retryable: true } },
				print: { state: 'not_created' }
			}
		});
		expect(preparationIsApprovedAndFresh(status)).toBe(true);
		expect(preparationUiState(status)).toBe('ready');
		expect(lessonArtifactUi(status, 'learn').state).toBe('failed');
		expect(lessonArtifactUi(status, 'learn').retryable).toBe(true);
	});

	it('does not guess identities or readiness from debug fields when the workspace is absent', () => {
		const status = base({
			generation_id: 'debug-generation', generation_status: 'ready', workflow_stage: 'ready',
			print_output_id: 'legacy-print', print_open_href: '/studio/print/legacy-print',
			workspace: undefined
		});
		expect(preparationUiState(status)).toBe('needs_attention');
		expect(resolvePlanGenerationId(status)).toBeNull();
		expect(resolvePrintGenerationId(status)).toBeNull();
		expect(lessonArtifactUi(status, 'print')).toMatchObject({ state: 'needs_attention', legacyAmbiguous: true, outputId: null, retryable: false });
		const emptyLegacy = base({ workspace: undefined, generation_id: null, generation_status: '', workflow_stage: 'unprepared' });
		expect(preparationUiState(emptyLegacy)).toBe('needs_attention');
		expect(lessonArtifactUi(emptyLegacy, 'learn')).toMatchObject({ state: 'needs_attention', legacyAmbiguous: true });
	});

	it('keeps Learn and Print identities independent', () => {
		const status = base({
			workspace: {
				preparation: { state: 'approved', approved_snapshot_verified: true },
				learn: { state: 'ready', realization_id: 'lr', output_id: 'lo', open_href: '/builder/from-native-learn/lo' },
				print: { state: 'not_created' }
			}
		});
		expect(lessonArtifactUi(status, 'learn')).toMatchObject({ state: 'ready', realizationId: 'lr', outputId: 'lo' });
		expect(lessonArtifactUi(status, 'print')).toMatchObject({ state: 'not_created', realizationId: null, outputId: null });
		expect(resolvePrintGenerationId(status)).toBeNull();
	});

	it('only advertises explicit retryable recoverable failures', () => {
		const status = base({
			workspace: {
				preparation: { state: 'approved', approved_snapshot_verified: true },
				learn: { state: 'failed_recoverable', realization_id: 'lr', error: { retryable: true } },
				print: { state: 'failed_terminal', realization_id: 'pr', stale: true, error: { retryable: true, recovery_action: 'reprepare' } }
			}
		});
		expect(lessonArtifactUi(status, 'learn').retryable).toBe(true);
		expect(lessonArtifactUi(status, 'print')).toMatchObject({ retryable: false, recoveryAction: 'reprepare' });
	});

	it.each([
		['MODEL_OUTPUT_INVALID', 'failed_recoverable', true, null, 'Section 2 failed validation.'],
		['PROVIDER_FAILURE', 'failed_terminal', false, null, 'Provider credentials were rejected.'],
		['REALIZATION_STALE', 'failed_terminal', false, 'reprepare', 'The approved plan changed.']
	] as const)('maps typed %s failures to teacher retry guidance', (code, state, retryable, recoveryAction, message) => {
		const status = base({
			workspace: {
				preparation: { state: 'approved', approved_snapshot_verified: true },
				learn: {
					state,
					realization_id: 'learn-failed',
					output_id: 'learn-output',
					error: { code, failure_class: 'validation', retryable, recovery_action: recoveryAction, message }
				},
				print: { state: 'not_created' }
			}
		});
		expect(lessonArtifactUi(status, 'learn')).toMatchObject({
			state: state === 'failed_recoverable' ? 'failed' : 'needs_attention',
			errorSummary: message,
			retryable,
			recoveryAction
		});
	});

	it('does not turn ready into retryable when preview fetch fails', () => {
		const status = base({
			workspace: {
				preparation: { state: 'approved', approved_snapshot_verified: true },
				learn: { state: 'ready', realization_id: 'lr', output_id: 'lo' },
				print: { state: 'ready', realization_id: 'pr', output_id: 'po', open_href: '/studio/print/po' }
			}
		});
		expect(lessonArtifactUi(status, 'print', 'preview unavailable')).toMatchObject({ state: 'ready', retryable: false, errorSummary: 'preview unavailable' });
		expect(resolvePrintGenerationId(status)).toBe('po');
	});
});
