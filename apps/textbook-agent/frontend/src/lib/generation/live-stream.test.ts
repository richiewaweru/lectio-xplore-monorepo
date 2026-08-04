import { describe, expect, it } from 'vitest';

import { applyGenerationStreamEvent, type GenerationStreamContext } from './live-stream';
import type { GenerationDocument } from '$lib/types';

function createContext(overrides: Partial<GenerationStreamContext> = {}): GenerationStreamContext {
	return {
		document: null,
		plannedSections: null,
		qcSummary: null,
		progressUpdate: null,
		runtimePolicy: null,
		runtimeProgress: null,
		viewerWarning: null,
		activeSectionId: null,
		sectionSignals: {},
		...overrides
	};
}

function createDocument(overrides: Partial<GenerationDocument> = {}): GenerationDocument {
	return {
		generation_id: 'gen-1',
		subject: 'Calculus',
		context: 'Explain limits',
		mode: 'balanced',
		template_id: 'guided-concept-path',
		preset_id: 'blue-classroom',
		status: 'running',
		section_manifest: [],
		sections: [],
		failed_sections: [],
		qc_reports: [],
		quality_passed: null,
		error: null,
		created_at: '2026-04-14T00:00:00Z',
		updated_at: '2026-04-14T00:00:00Z',
		completed_at: null,
		...overrides
	};
}

describe('live-stream helpers', () => {
	it('normalizes runtime progress to media counters', () => {
		const result = applyGenerationStreamEvent(
			createContext(),
			'runtime_progress',
			JSON.stringify({
				type: 'runtime_progress',
				generation_id: 'gen-1',
				snapshot: {
					mode: 'balanced',
					sections_total: 2,
					sections_completed: 0,
					sections_running: 1,
					sections_queued: 1,
					media_running: 1,
					media_queued: 0,
					qc_running: 0,
					qc_queued: 0,
					retry_running: 0,
					retry_queued: 0
				},
				emitted_at: '2026-04-14T00:00:00Z'
			})
		);

		expect(result.next.runtimeProgress?.media_running).toBe(1);
		expect(result.next.runtimeProgress?.media_queued).toBe(0);
	});

	it('returns the same context for duplicate runtime progress', () => {
		const context = createContext({
			plannedSections: 2,
			runtimeProgress: {
				mode: 'balanced',
				sections_total: 2,
				sections_completed: 1,
				sections_running: 0,
				sections_queued: 1,
				media_running: 1,
				media_queued: 0,
				qc_running: 0,
				qc_queued: 0,
				retry_running: 0,
				retry_queued: 0
			}
		});

		const result = applyGenerationStreamEvent(
			context,
			'runtime_progress',
			JSON.stringify({
				type: 'runtime_progress',
				generation_id: 'gen-1',
				snapshot: {
					mode: 'balanced',
					sections_total: 2,
					sections_completed: 1,
					sections_running: 0,
					sections_queued: 1,
					media_running: 1,
					media_queued: 0,
					qc_running: 0,
					qc_queued: 0,
					retry_running: 0,
					retry_queued: 0
				},
				emitted_at: '2026-04-14T00:00:00Z'
			})
		);

		expect(result.next).toBe(context);
	});

	it('returns the same context for duplicate progress updates', () => {
		const context = createContext({
			activeSectionId: 's-01',
			progressUpdate: {
				type: 'progress_update',
				generation_id: 'gen-1',
				stage: 'awaiting_assets',
				label: 'Generating media',
				section_id: 's-01'
			}
		});

		const result = applyGenerationStreamEvent(
			context,
			'progress_update',
			JSON.stringify({
				type: 'progress_update',
				generation_id: 'gen-1',
				stage: 'awaiting_assets',
				label: 'Generating media',
				section_id: 's-01'
			})
		);

		expect(result.next).toBe(context);
	});

	it('keeps section_started as a manifest update without marking the section active', () => {
		const context = createContext({
			document: createDocument({
				section_manifest: []
			})
		});

		const result = applyGenerationStreamEvent(
			context,
			'section_started',
			JSON.stringify({
				type: 'section_started',
				generation_id: 'gen-1',
				section_id: 's-01',
				title: 'First section',
				position: 1
			})
		);

		expect(result.next.document?.section_manifest).toEqual([
			{ section_id: 's-01', title: 'First section', position: 1 }
		]);
		expect(result.next.activeSectionId).toBeNull();
		expect(result.next.sectionSignals).toEqual({});
	});

	it('marks only the targeted section as generating for a generating_section progress update', () => {
		const context = createContext({
			sectionSignals: {
				's-02': { status: 'planned' }
			}
		});

		const result = applyGenerationStreamEvent(
			context,
			'progress_update',
			JSON.stringify({
				type: 'progress_update',
				generation_id: 'gen-1',
				stage: 'generating_section',
				label: 'Generating section',
				section_id: 's-01'
			})
		);

		expect(result.next.activeSectionId).toBe('s-01');
		expect(result.next.sectionSignals['s-01']).toEqual({
			status: 'generating',
			label: 'Generating section'
		});
		expect(result.next.sectionSignals['s-02']).toEqual({ status: 'planned' });
	});

	it('marks only the targeted section as repairing for a repairing progress update', () => {
		const context = createContext({
			sectionSignals: {
				's-02': { status: 'planned' }
			}
		});

		const result = applyGenerationStreamEvent(
			context,
			'progress_update',
			JSON.stringify({
				type: 'progress_update',
				generation_id: 'gen-1',
				stage: 'repairing',
				label: 'Repairing section',
				section_id: 's-01'
			})
		);

		expect(result.next.activeSectionId).toBe('s-01');
		expect(result.next.sectionSignals['s-01']).toEqual({
			status: 'generating',
			label: 'Repairing section'
		});
		expect(result.next.sectionSignals['s-02']).toEqual({ status: 'planned' });
	});

	it('tracks required media blocks at section level', () => {
		const result = applyGenerationStreamEvent(
			createContext(),
			'section_media_blocked',
			JSON.stringify({
				type: 'section_media_blocked',
				generation_id: 'gen-1',
				section_id: 's-01',
				slot_ids: ['diagram-main'],
				reason: 'Required media is still incomplete.',
				blocked_at: '2026-04-14T00:00:00Z'
			})
		);

		expect(result.next.sectionSignals['s-01']).toEqual({
			status: 'blocked_by_required_media',
			reason: 'Required media is still incomplete.',
			slot_ids: ['diagram-main']
		});
	});

	it('ignores stale media activity for a ready section', () => {
		const context = createContext({
			sectionSignals: {
				's-01': { status: 'ready' }
			}
		});

		const result = applyGenerationStreamEvent(
			context,
			'media_frame_started',
			JSON.stringify({
				type: 'media_frame_started',
				generation_id: 'gen-1',
				section_id: 's-01',
				slot_id: 'diagram-main',
				slot_type: 'diagram',
				frame_key: 'frame-1',
				frame_index: 0,
				started_at: '2026-04-14T00:00:00Z'
			})
		);

		expect(result.next).toBe(context);
	});

	it('ignores stale media activity for a failed section', () => {
		const context = createContext({
			sectionSignals: {
				's-01': { status: 'failed' }
			}
		});

		const result = applyGenerationStreamEvent(
			context,
			'media_slot_ready',
			JSON.stringify({
				type: 'media_slot_ready',
				generation_id: 'gen-1',
				section_id: 's-01',
				slot_id: 'diagram-main',
				slot_type: 'diagram',
				ready_frames: 1,
				total_frames: 1,
				ready_at: '2026-04-14T00:00:00Z'
			})
		);

		expect(result.next).toBe(context);
	});

	it('still applies terminal section events after prior activity', () => {
		const context = createContext({
			document: createDocument({
				section_manifest: [{ section_id: 's-01', title: 'First section', position: 1 }]
			}),
			activeSectionId: 's-01',
			sectionSignals: {
				's-01': { status: 'partially_ready' }
			}
		});

		const result = applyGenerationStreamEvent(
			context,
			'section_ready',
			JSON.stringify({
				type: 'section_ready',
				generation_id: 'gen-1',
				section_id: 's-01',
				section: {
					section_id: 's-01',
					template_id: 'guided-concept-path',
					header: {
						title: 'First section',
						subject: 'Calculus',
						grade_band: 'secondary'
					},
					hook: {
						headline: 'Start here',
						body: 'Look nearby.',
						anchor: 'limits'
					},
					explanation: {
						body: 'Limits study nearby behavior.',
						emphasis: ['nearby']
					},
					practice: {
						problems: [
							{
								difficulty: 'warm',
								question: 'What happens near x = 2?',
								hints: [{ level: 1, text: 'Look near 2.' }]
							},
							{
								difficulty: 'medium',
								question: 'Estimate the limit.',
								hints: [{ level: 1, text: 'Compare nearby values.' }]
							}
						]
					},
					what_next: {
						body: 'Now connect this to continuity.',
						next: 'Continuity'
					}
				},
				completed_sections: 1,
				total_sections: 1
			})
		);

		expect(result.next.sectionSignals['s-01']).toEqual({ status: 'ready' });
		expect(result.next.activeSectionId).toBeNull();
	});
});
