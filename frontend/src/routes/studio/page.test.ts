// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const navigationMocks = vi.hoisted(() => ({
	goto: vi.fn()
}));

const mocks = vi.hoisted(() => ({
	approveChunkedPlan: vi.fn(),
	adjustBlueprint: vi.fn(),
	connectV3ChunkedStream: vi.fn(() => vi.fn()),
	connectV3StudioGenerationStream: vi.fn(() => vi.fn()),
	getChunkedPlanStatus: vi.fn(),
	downloadV3GenerationPdf: vi.fn(),
	extractSignals: vi.fn(),
	fetchV3Document: vi.fn(),
	getV3GenerationBlueprint: vi.fn(),
	regenerateChunkedPlan: vi.fn(),
	retryChunkedSection: vi.fn(),
	startChunkedPlan: vi.fn()
}));

const builderMocks = vi.hoisted(() => ({
	createBuilderLesson: vi.fn(),
	saveDocument: vi.fn(),
	v3PackToBuilderDocument: vi.fn()
}));

vi.mock('$app/navigation', () => ({
	goto: navigationMocks.goto
}));

vi.mock('$lib/api/v3', () => ({
	approveChunkedPlan: mocks.approveChunkedPlan,
	adjustBlueprint: mocks.adjustBlueprint,
	connectV3ChunkedStream: mocks.connectV3ChunkedStream,
	connectV3StudioGenerationStream: mocks.connectV3StudioGenerationStream,
	getChunkedPlanStatus: mocks.getChunkedPlanStatus,
	downloadV3GenerationPdf: mocks.downloadV3GenerationPdf,
	extractSignals: mocks.extractSignals,
	fetchV3Document: mocks.fetchV3Document,
	getV3GenerationBlueprint: mocks.getV3GenerationBlueprint,
	regenerateChunkedPlan: mocks.regenerateChunkedPlan,
	retryChunkedSection: mocks.retryChunkedSection,
	startChunkedPlan: mocks.startChunkedPlan
}));

vi.mock('$lib/builder/api/lesson-crud', () => ({
	createBuilderLesson: builderMocks.createBuilderLesson
}));

vi.mock('$lib/builder/persistence/idb-store', () => ({
	saveDocument: builderMocks.saveDocument
}));

vi.mock('$lib/builder/adapters/from-generation', () => ({
	v3PackToBuilderDocument: builderMocks.v3PackToBuilderDocument
}));

vi.mock('$lib/components/studio/V3InputSurface.svelte', async () => ({
	default: (await import('./__fixtures__/MockGeneric.svelte')).default
}));
vi.mock('$lib/components/studio/V3PlanningState.svelte', async () => ({
	default: (await import('./__fixtures__/MockGeneric.svelte')).default
}));
vi.mock('$lib/components/studio/V3SignalConfirmation.svelte', async () => ({
	default: (await import('./__fixtures__/MockGeneric.svelte')).default
}));
vi.mock('$lib/components/studio/V3BlueprintPreview.svelte', async () => ({
	default: (await import('./__fixtures__/MockGeneric.svelte')).default
}));
vi.mock('$lib/components/studio/V3Canvas.svelte', async () => ({
	default: (await import('./__fixtures__/MockGeneric.svelte')).default
}));
vi.mock('$lib/components/studio/V3BookletPackView.svelte', async () => ({
	default: (await import('./__fixtures__/MockGeneric.svelte')).default
}));
import StudioPage from './+page.svelte';
import { resetV3Studio, v3Studio } from '$lib/stores/v3-studio.svelte';

function deferred<T>() {
	let resolve!: (value: T) => void;
	let reject!: (reason?: unknown) => void;
	const promise = new Promise<T>((res, rej) => {
		resolve = res;
		reject = rej;
	});
	return { promise, resolve, reject };
}

function latestChunkedHandlers(): unknown {
	return (mocks.connectV3ChunkedStream.mock.calls as unknown as Array<[string, unknown]>).at(-1)?.[1];
}

function latestGenerationHandlers(): unknown {
	return (mocks.connectV3StudioGenerationStream.mock.calls as unknown as Array<[string, unknown]>).at(-1)?.[1];
}

describe('studio chunked URL resume', () => {
	beforeEach(() => {
		resetV3Studio();
		navigationMocks.goto.mockReset();
		mocks.approveChunkedPlan.mockReset();
		mocks.connectV3ChunkedStream.mockReset();
		mocks.connectV3ChunkedStream.mockImplementation(() => vi.fn());
		mocks.connectV3StudioGenerationStream.mockReset();
		mocks.connectV3StudioGenerationStream.mockImplementation(() => vi.fn());
		mocks.getChunkedPlanStatus.mockReset();
		mocks.fetchV3Document.mockReset();
		mocks.getV3GenerationBlueprint.mockReset();
		builderMocks.createBuilderLesson.mockReset();
		builderMocks.saveDocument.mockReset();
		builderMocks.v3PackToBuilderDocument.mockReset();
		window.history.replaceState({}, '', '/studio');
	});

	afterEach(() => {
		cleanup();
		vi.useRealTimers();
	});

	it('hydrates plan review from generation_id query when plan is ready', async () => {
		window.history.replaceState({}, '', '/studio?generation_id=gen-plan');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-plan',
			stage: 'plan_ready',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: false,
			next_action: 'approve_or_regenerate'
		});

		render(StudioPage);

		await waitFor(() => expect(mocks.getChunkedPlanStatus).toHaveBeenCalledWith('gen-plan'));
		expect(await screen.findByText('Structural plan')).toBeTruthy();
		expect(await screen.findByRole('button', { name: /adjust \(regenerate with note\)/i })).toBeTruthy();
		expect(v3Studio.stage).toBe('skeleton');
		expect(mocks.connectV3StudioGenerationStream).not.toHaveBeenCalled();
	});

	it('reconnects stream for in-flight stage2 on URL resume', async () => {
		window.history.replaceState({}, '', '/studio?generation_id=gen-live');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-live',
			stage: 'stage2_running',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [
					{
						id: 'intro',
						title: 'Intro',
						role: 'intro',
						visual_required: false,
						transition_note: null,
						components: []
					}
				],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: true,
			next_action: 'wait_for_stage2'
		});
		mocks.approveChunkedPlan.mockResolvedValue({
			generation_id: 'gen-live',
			stage: 'stage2_running',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [
					{
						id: 'intro',
						title: 'Intro',
						role: 'intro',
						visual_required: false,
						transition_note: null,
						components: []
					}
				],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: true,
			next_action: 'wait_for_stage2'
		});

		render(StudioPage);

		await waitFor(() => expect(mocks.getChunkedPlanStatus).toHaveBeenCalledWith('gen-live'));
		await waitFor(() => expect(mocks.approveChunkedPlan).toHaveBeenCalledWith('gen-live'));
		await waitFor(() => expect(mocks.connectV3ChunkedStream).toHaveBeenCalledWith('gen-live', expect.any(Object)));
		expect(v3Studio.stage).toBe('fill');
	});

	it('keeps planning after approve while stage2 is still running', async () => {
		window.history.replaceState({}, '', '/studio?generation_id=gen-approve');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-approve',
			stage: 'plan_ready',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: false,
			next_action: 'approve_or_regenerate'
		});
		const approval = deferred<{
			generation_id: string;
			stage: 'stage2_running';
			structural_plan: {
				lesson_mode: string;
				lesson_intent: { goal: string; structure_rationale: string };
				anchor: { example: string; reuse_scope: string };
				sections: never[];
				question_plan: never[];
			};
			section_briefs: Record<string, never>;
			failed_sections: never[];
			blueprint_id: null;
			execution_started: true;
			next_action: 'wait_for_stage2';
		}>();
		mocks.approveChunkedPlan.mockReturnValue(approval.promise);

		render(StudioPage);
		await waitFor(() => expect(mocks.getChunkedPlanStatus).toHaveBeenCalledWith('gen-approve'));

		await fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));

		await waitFor(() =>
			expect(mocks.approveChunkedPlan).toHaveBeenCalledWith('gen-approve', {
				display_title: 'Goal'
			})
		);
		expect(v3Studio.stage).toBe('fill');
		expect(v3Studio.canvas).toHaveLength(0);
		expect(mocks.connectV3StudioGenerationStream).not.toHaveBeenCalled();

		approval.resolve({
			generation_id: 'gen-approve',
			stage: 'stage2_running',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: true,
			next_action: 'wait_for_stage2'
		});
		await waitFor(() =>
			expect(mocks.connectV3ChunkedStream).toHaveBeenCalledWith('gen-approve', expect.any(Object))
		);
		expect(v3Studio.stage).toBe('fill');
		await waitFor(() => expect(mocks.fetchV3Document).toHaveBeenCalledWith('gen-approve'));
	});

	it('does not connect the stream when approve returns true assembly_blocked', async () => {
		window.history.replaceState({}, '', '/studio?generation_id=gen-approve-blocked');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-approve-blocked',
			stage: 'plan_ready',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: false,
			next_action: 'approve_or_regenerate'
		});
		mocks.approveChunkedPlan.mockResolvedValue({
			generation_id: 'gen-approve-blocked',
			stage: 'assembly_blocked',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: ['intro'],
			blueprint_id: null,
			execution_started: false,
			next_action: 'retry_failed_sections'
		});

		render(StudioPage);
		await waitFor(() =>
			expect(mocks.getChunkedPlanStatus).toHaveBeenCalledWith('gen-approve-blocked')
		);

		await fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));

		await waitFor(() =>
			expect(mocks.approveChunkedPlan).toHaveBeenCalledWith('gen-approve-blocked', {
				display_title: 'Goal'
			})
		);
		expect(v3Studio.stage).toBe('skeleton');
		expect(mocks.connectV3StudioGenerationStream).not.toHaveBeenCalled();
	});

	it('starts document polling at approve even when streams deliver no events', async () => {
		vi.useFakeTimers();
		window.history.replaceState({}, '', '/studio?generation_id=gen-poll-approve');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-poll-approve',
			stage: 'plan_ready',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: false,
			next_action: 'approve_or_regenerate'
		});
		mocks.approveChunkedPlan.mockResolvedValue({
			generation_id: 'gen-poll-approve',
			stage: 'stage2_running',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: true,
			next_action: 'wait_for_stage2'
		});
		mocks.fetchV3Document
			.mockRejectedValueOnce(Object.assign(new Error('Document not found'), { status: 404 }))
			.mockRejectedValueOnce(Object.assign(new Error('Document not found'), { status: 404 }))
			.mockResolvedValueOnce({
				kind: 'v3_booklet_pack',
				generation_id: 'gen-poll-approve',
				template_id: 'guided-concept-path',
				subject: 'Mathematics',
				status: 'streaming_preview',
				progress: {
					stage: 'writing',
					sections: { build: 'ready' },
					updated_at: '2026-07-11T00:00:08Z'
				},
				section_diagnostics: [],
				sections: [{ section_id: 'build', header: { title: 'Build understanding' } }],
				warnings: [],
				booklet_issues: []
			})
			.mockResolvedValueOnce({
				kind: 'v3_booklet_pack',
				generation_id: 'gen-poll-approve',
				template_id: 'guided-concept-path',
				subject: 'Mathematics',
				status: 'final_ready',
				progress: {
					stage: 'completed',
					sections: { build: 'ready' },
					updated_at: '2026-07-11T00:00:12Z'
				},
				section_diagnostics: [],
				sections: [{ section_id: 'build', header: { title: 'Build understanding' } }],
				warnings: [],
				booklet_issues: []
			});

		render(StudioPage);
		await waitFor(() =>
			expect(mocks.getChunkedPlanStatus).toHaveBeenCalledWith('gen-poll-approve')
		);
		await fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));

		await waitFor(() => expect(mocks.fetchV3Document).toHaveBeenCalledTimes(1));
		await vi.advanceTimersByTimeAsync(4000);
		await waitFor(() => expect(mocks.fetchV3Document).toHaveBeenCalledTimes(2));
		await vi.advanceTimersByTimeAsync(4000);
		await waitFor(() => expect(mocks.fetchV3Document).toHaveBeenCalledTimes(3));
		expect(v3Studio.canvas[0]?.id).toBe('build');
		await vi.advanceTimersByTimeAsync(4000);
		await waitFor(() => expect(mocks.fetchV3Document).toHaveBeenCalledTimes(4));
		expect(v3Studio.stage).toBe('edit');

		await vi.advanceTimersByTimeAsync(8000);
		expect(mocks.fetchV3Document).toHaveBeenCalledTimes(4);
		expect(mocks.connectV3StudioGenerationStream).not.toHaveBeenCalled();
	});

	it('does not start document polling when approve returns assembly_blocked', async () => {
		vi.useFakeTimers();
		window.history.replaceState({}, '', '/studio?generation_id=gen-poll-blocked');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-poll-blocked',
			stage: 'plan_ready',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: false,
			next_action: 'approve_or_regenerate'
		});
		mocks.approveChunkedPlan.mockResolvedValue({
			generation_id: 'gen-poll-blocked',
			stage: 'assembly_blocked',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: ['intro'],
			blueprint_id: null,
			execution_started: false,
			next_action: 'retry_failed_sections'
		});

		render(StudioPage);
		await waitFor(() =>
			expect(mocks.getChunkedPlanStatus).toHaveBeenCalledWith('gen-poll-blocked')
		);
		await fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));
		await waitFor(() => expect(v3Studio.stage).toBe('skeleton'));

		await vi.advanceTimersByTimeAsync(8000);
		expect(mocks.fetchV3Document).not.toHaveBeenCalled();
	});

	it('starts document polling when resuming a running generation without stream events', async () => {
		vi.useFakeTimers();
		window.history.replaceState({}, '', '/studio?generation_id=gen-resume-poll');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-resume-poll',
			stage: 'stage2_running',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: true,
			next_action: 'wait_for_stage2'
		});
		mocks.approveChunkedPlan.mockResolvedValue({
			generation_id: 'gen-resume-poll',
			stage: 'stage2_running',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: true,
			next_action: 'wait_for_stage2'
		});
		mocks.fetchV3Document.mockRejectedValue(Object.assign(new Error('Document not found'), { status: 404 }));

		render(StudioPage);

		await waitFor(() => expect(mocks.fetchV3Document).toHaveBeenCalledWith('gen-resume-poll'));
		await vi.advanceTimersByTimeAsync(4000);
		await waitFor(() => expect(mocks.fetchV3Document).toHaveBeenCalledTimes(2));
		expect(mocks.connectV3StudioGenerationStream).not.toHaveBeenCalled();
	});

	it('keeps polling quietly when the document is not ready yet', async () => {
		vi.useFakeTimers();
		window.history.replaceState({}, '', '/studio?generation_id=gen-quiet-404');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-quiet-404',
			stage: 'stage2_running',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: true,
			next_action: 'wait_for_stage2'
		});
		mocks.approveChunkedPlan.mockResolvedValue({
			generation_id: 'gen-quiet-404',
			stage: 'stage2_running',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: true,
			next_action: 'wait_for_stage2'
		});
		mocks.fetchV3Document.mockRejectedValue(Object.assign(new Error('Document not found'), { status: 404 }));

		render(StudioPage);

		await waitFor(() => expect(mocks.fetchV3Document).toHaveBeenCalledTimes(1));
		expect(v3Studio.error).toBeNull();
		await vi.advanceTimersByTimeAsync(4000);
		await waitFor(() => expect(mocks.fetchV3Document).toHaveBeenCalledTimes(2));
		expect(v3Studio.error).toBeNull();
	});

	it('switches from chunked SSE to generation SSE after stage2 completes', async () => {
		window.history.replaceState({}, '', '/studio?generation_id=gen-switch');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-switch',
			stage: 'plan_ready',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [{ id: 'intro', title: 'Intro', role: 'intro', visual_required: false, transition_note: null, components: [] }],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: false,
			next_action: 'approve_or_regenerate'
		});
		mocks.approveChunkedPlan.mockResolvedValue({
			generation_id: 'gen-switch',
			stage: 'stage2_running',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [{ id: 'intro', title: 'Intro', role: 'intro', visual_required: false, transition_note: null, components: [] }],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: true,
			next_action: 'wait_for_stage2'
		});
		const disconnectChunked = vi.fn();
		mocks.connectV3ChunkedStream.mockReturnValue(disconnectChunked);

		render(StudioPage);
		await waitFor(() => expect(mocks.getChunkedPlanStatus).toHaveBeenCalledWith('gen-switch'));
		await fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));
		await waitFor(() => expect(mocks.connectV3ChunkedStream).toHaveBeenCalledWith('gen-switch', expect.any(Object)));

		const handlers = latestChunkedHandlers() as {
			onStage2Complete?: (failedSections: string[]) => void;
		};
		handlers.onStage2Complete?.([]);

		await waitFor(() =>
			expect(mocks.connectV3StudioGenerationStream).toHaveBeenCalledWith(
				'gen-switch',
				expect.any(Object)
			)
		);
		expect(disconnectChunked).toHaveBeenCalled();
	});

	it('keeps generation SSE alive when chunked stage2 completes with partial failures', async () => {
		window.history.replaceState({}, '', '/studio?generation_id=gen-failed');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-failed',
			stage: 'plan_ready',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [{ id: 'intro', title: 'Intro', role: 'intro', visual_required: false, transition_note: null, components: [] }],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: false,
			next_action: 'approve_or_regenerate'
		});
		mocks.approveChunkedPlan.mockResolvedValue({
			generation_id: 'gen-failed',
			stage: 'stage2_running',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [{ id: 'intro', title: 'Intro', role: 'intro', visual_required: false, transition_note: null, components: [] }],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: true,
			next_action: 'wait_for_stage2'
		});
		const disconnectChunked = vi.fn();
		mocks.connectV3ChunkedStream.mockReturnValue(disconnectChunked);

		render(StudioPage);
		await waitFor(() => expect(mocks.getChunkedPlanStatus).toHaveBeenCalledWith('gen-failed'));
		await fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));
		await waitFor(() => expect(mocks.connectV3ChunkedStream).toHaveBeenCalled());

		const handlers = latestChunkedHandlers() as {
			onStage2Complete?: (failedSections: string[]) => void;
			onAssemblyBlocked?: (failedSections: string[]) => void;
		};
		handlers.onStage2Complete?.(['intro']);
		expect(v3Studio.stage).toBe('fill');
		expect(disconnectChunked).toHaveBeenCalled();
		await waitFor(() =>
			expect(mocks.connectV3StudioGenerationStream).toHaveBeenCalledWith(
				'gen-failed',
				expect.any(Object)
			)
		);
		expect(v3Studio.chunkedState?.failed_sections).toEqual(['intro']);

		handlers.onAssemblyBlocked?.(['intro']);
		expect(v3Studio.stage).toBe('skeleton');
	});

	it('shows stage2 section pills updating from chunked SSE events', async () => {
		window.history.replaceState({}, '', '/studio?generation_id=gen-pills');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-pills',
			stage: 'stage2_running',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [
					{ id: 'intro', title: 'Intro', role: 'intro', visual_required: false, transition_note: null, components: [] },
					{ id: 'model', title: 'Model', role: 'model', visual_required: false, transition_note: null, components: [] }
				],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: true,
			next_action: 'wait_for_stage2'
		});
		mocks.approveChunkedPlan.mockResolvedValue({
			generation_id: 'gen-pills',
			stage: 'stage2_running',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [
					{ id: 'intro', title: 'Intro', role: 'intro', visual_required: false, transition_note: null, components: [] },
					{ id: 'model', title: 'Model', role: 'model', visual_required: false, transition_note: null, components: [] }
				],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: true,
			next_action: 'wait_for_stage2'
		});

		render(StudioPage);
		await waitFor(() => expect(mocks.connectV3ChunkedStream).toHaveBeenCalledWith('gen-pills', expect.any(Object)));

		const handlers = latestChunkedHandlers() as {
			onSectionStart?: (sectionId: string) => void;
			onSectionDone?: (
				sectionId: string,
				brief?: {
					components: { component_id: string; content_intent: string }[];
					question_prompts: string[];
					visual_subject: string | null;
				}
			) => void;
			onSectionFailed?: (sectionId: string, errors: string[]) => void;
		};
		const intro = await screen.findByText('intro');
		const model = await screen.findByText('model');

		handlers.onSectionStart?.('intro');
		await waitFor(() => expect(intro.className).toContain('active'));
		expect(v3Studio.canvas[0]?.sectionStatus).toBe('running');

		handlers.onSectionDone?.('intro', {
			components: [{ component_id: 'hook-hero', content_intent: 'Open with a concrete anchor.' }],
			question_prompts: ['Which two fractions show the same amount?'],
			visual_subject: 'Fraction strip comparison'
		});
		await waitFor(() => expect(intro.className).toContain('done'));
		expect(v3Studio.canvas[0]?.sectionStatus).toBe('complete');
		expect(v3Studio.canvas[0]?.stage2Preview).toEqual({
			componentIntents: [{ componentId: 'hook-hero', intent: 'Open with a concrete anchor.' }],
			questionPrompts: ['Which two fractions show the same amount?'],
			visualSubject: 'Fraction strip comparison'
		});

		handlers.onSectionFailed?.('model', ['boom']);
		await waitFor(() => expect(model.className).toContain('failed'));
		expect(v3Studio.canvas[1]?.sectionStatus).toBe('failed');
	});

	it('fails soft when generation_id cannot be resumed', async () => {
		window.history.replaceState({}, '', '/studio?generation_id=gen-missing');
		mocks.getChunkedPlanStatus.mockRejectedValue(new Error('404'));

		render(StudioPage);

		await waitFor(() => expect(mocks.getChunkedPlanStatus).toHaveBeenCalledWith('gen-missing'));
		await waitFor(() => expect(v3Studio.stage).toBe('intent'));
		expect(await screen.findByRole('alert')).toBeTruthy();
		expect(screen.getByRole('alert').textContent).toMatch(/could not resume/i);
	});

	it('keeps planning when blocked retry returns to stage2_running', async () => {
		window.history.replaceState({}, '', '/studio?generation_id=gen-blocked');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-blocked',
			stage: 'assembly_blocked',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [
					{
						id: 'intro',
						title: 'Intro',
						role: 'intro',
						visual_required: false,
						transition_note: null,
						components: []
					}
				],
				question_plan: []
			},
			section_briefs: { intro: null },
			failed_sections: ['intro'],
			blueprint_id: null,
			execution_started: false,
			next_action: 'retry_failed_sections'
		});
		mocks.retryChunkedSection.mockResolvedValue({
			generation_id: 'gen-blocked',
			stage: 'stage2_running',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [
					{
						id: 'intro',
						title: 'Intro',
						role: 'intro',
						visual_required: false,
						transition_note: null,
						components: []
					}
				],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: true,
			next_action: 'wait_for_stage2'
		});

		render(StudioPage);
		await waitFor(() => expect(mocks.getChunkedPlanStatus).toHaveBeenCalledWith('gen-blocked'));
		expect(v3Studio.stage).toBe('skeleton');

		await fireEvent.click(await screen.findByRole('button', { name: /retry intro/i }));
		await waitFor(() =>
			expect(mocks.retryChunkedSection).toHaveBeenCalledWith({
				generation_id: 'gen-blocked',
				section_id: 'intro'
			})
		);
		await waitFor(() => expect(v3Studio.stage).toBe('fill'));
		await waitFor(() => expect(mocks.connectV3ChunkedStream).toHaveBeenCalledWith('gen-blocked', expect.any(Object)));
	});

	it('enters generating and recovers blueprint preview when chunked state is blueprint_ready', async () => {
		window.history.replaceState({}, '', '/studio?generation_id=gen-blueprint');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-blueprint',
			stage: 'blueprint_ready',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: 'bp-1',
			execution_started: true,
			next_action: 'generation_running'
		});
		mocks.getV3GenerationBlueprint.mockResolvedValue({
			blueprint_id: 'bp-1',
			template_id: 'guided-concept-path',
			sections: []
		});

		render(StudioPage);

		await waitFor(() => expect(mocks.getChunkedPlanStatus).toHaveBeenCalledWith('gen-blueprint'));
		await waitFor(() =>
			expect(mocks.connectV3StudioGenerationStream).toHaveBeenCalledWith(
				'gen-blueprint',
				expect.any(Object)
			)
		);
		await waitFor(() => expect(mocks.getV3GenerationBlueprint).toHaveBeenCalledWith('gen-blueprint'));
		expect(v3Studio.stage).toBe('fill');
	});

	it('paints the structural plan into the canvas immediately on approve', async () => {
		window.history.replaceState({}, '', '/studio?generation_id=gen-canvas');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-canvas',
			stage: 'plan_ready',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [
					{
						id: 'orient',
						title: 'Orient',
						role: 'orient',
						visual_required: true,
						transition_note: null,
						components: [{ slug: 'hook-hero', purpose: 'Open the lesson' }]
					}
				],
				question_plan: [{ question_id: 'q1', section_id: 'orient', temperature: 'warm', diagram_required: false }]
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: false,
			next_action: 'approve_or_regenerate'
		});
		const approval = deferred<{
			generation_id: string;
			stage: 'stage2_running';
			structural_plan: {
				lesson_mode: string;
				lesson_intent: { goal: string; structure_rationale: string };
				anchor: { example: string; reuse_scope: string };
				sections: Array<Record<string, unknown>>;
				question_plan: Array<Record<string, unknown>>;
			};
			section_briefs: Record<string, never>;
			failed_sections: never[];
			blueprint_id: null;
			execution_started: true;
			next_action: 'wait_for_stage2';
		}>();
		mocks.approveChunkedPlan.mockReturnValue(approval.promise);

		render(StudioPage);
		await waitFor(() => expect(mocks.getChunkedPlanStatus).toHaveBeenCalledWith('gen-canvas'));
		await fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));

		expect(v3Studio.stage).toBe('fill');
		expect(v3Studio.canvas).toHaveLength(1);
		expect(v3Studio.canvas[0]?.id).toBe('orient');
		expect(v3Studio.canvas[0]?.components[0]?.id).toBe('hook-hero');
		expect(v3Studio.canvas[0]?.visual?.status).toBe('pending');
	});

	it('repaints the canvas from polled draft snapshots during generation', async () => {
		window.history.replaceState({}, '', '/studio?generation_id=gen-snapshot');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-snapshot',
			stage: 'blueprint_ready',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: 'bp-1',
			execution_started: true,
			next_action: 'generation_running'
		});
		mocks.getV3GenerationBlueprint.mockResolvedValue({
			blueprint_id: 'bp-1',
			template_id: 'guided-concept-path',
			section_plan: [],
			question_plan: [],
			resource_type: 'lesson',
			title: 'Test lesson',
			anchor: null,
			register_summary: '',
			support_summary: []
		});
		mocks.fetchV3Document
			.mockResolvedValueOnce({
				kind: 'v3_booklet_pack',
				generation_id: 'gen-snapshot',
				template_id: 'guided-concept-path',
				subject: 'Mathematics',
				status: 'streaming_preview',
				progress: {
					stage: 'writing',
					sections: { build: 'ready' },
					updated_at: '2026-07-11T00:00:00Z'
				},
				section_diagnostics: [
					{
						section_id: 'build',
						status: 'incomplete',
						renderable: true,
						missing_components: ['practice-stack'],
						missing_visuals: [],
						warnings: ['Missing practice block']
					}
				],
				sections: [{ section_id: 'build', header: { title: 'Build understanding' } }],
				warnings: [],
				booklet_issues: []
			})
			.mockResolvedValueOnce({
				kind: 'v3_booklet_pack',
				generation_id: 'gen-snapshot',
				template_id: 'guided-concept-path',
				subject: 'Mathematics',
				status: 'final_ready',
				progress: {
					stage: 'completed',
					sections: { practice: 'ready' },
					updated_at: '2026-07-11T00:00:04Z'
				},
				section_diagnostics: [
					{
						section_id: 'practice',
						status: 'complete',
						renderable: true,
						missing_components: [],
						missing_visuals: [],
						warnings: []
					}
				],
				sections: [{ section_id: 'practice', header: { title: 'Practice' } }],
				warnings: [],
				booklet_issues: []
			});

		render(StudioPage);
		await waitFor(() => expect(mocks.connectV3StudioGenerationStream).toHaveBeenCalled());
		await waitFor(() => expect(mocks.fetchV3Document).toHaveBeenCalledWith('gen-snapshot'));
		expect(v3Studio.canvas).toHaveLength(1);
		expect(v3Studio.canvas[0]?.id).toBe('build');
		expect(v3Studio.canvas[0]?.sectionStatus).toBe('incomplete');

		const handlers = latestGenerationHandlers() as {
			onPoke?: () => void;
		};
		handlers.onPoke?.();
		await waitFor(() => expect(mocks.fetchV3Document).toHaveBeenCalledTimes(2));
		expect(v3Studio.canvas).toHaveLength(1);
		expect(v3Studio.canvas[0]?.id).toBe('practice');
		expect(v3Studio.stage).toBe('edit');
	});

	it('rehydrates from the persisted document on generation reopen and stream error even with an active pack', async () => {
		window.history.replaceState({}, '', '/studio?generation_id=gen-reopen');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-reopen',
			stage: 'blueprint_ready',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: 'bp-reopen',
			execution_started: true,
			next_action: 'generation_running'
		});
		mocks.getV3GenerationBlueprint.mockResolvedValue({
			blueprint_id: 'bp-reopen',
			template_id: 'guided-concept-path',
			section_plan: [],
			question_plan: [],
			resource_type: 'lesson',
			title: 'Reconnect lesson',
			anchor: null,
			register_summary: '',
			support_summary: []
		});
		mocks.fetchV3Document.mockResolvedValue({
			kind: 'v3_booklet_pack',
			generation_id: 'gen-reopen',
			template_id: 'guided-concept-path',
			subject: 'Mathematics',
			status: 'draft_ready',
			sections: [{ section_id: 'recovered', header: { title: 'Recovered section' } }],
			warnings: [],
			section_diagnostics: [],
			booklet_issues: []
		});
		v3Studio.activePack = {
			generation_id: 'gen-reopen',
			blueprint_id: 'bp-stale',
			template_id: 'guided-concept-path',
			subject: 'Mathematics',
			status: 'draft_ready',
			sections: [{ section_id: 'stale', header: { title: 'Stale section' } }],
			warnings: [],
			section_diagnostics: [],
			booklet_issues: []
		};

		render(StudioPage);
		await waitFor(() => expect(mocks.connectV3StudioGenerationStream).toHaveBeenCalled());
		await waitFor(() => expect(mocks.fetchV3Document).toHaveBeenCalledWith('gen-reopen'));

		const handlers = latestGenerationHandlers() as {
			onOpen?: () => void;
			onError?: () => void;
		};

		handlers.onOpen?.();
		await waitFor(() => expect(mocks.fetchV3Document).toHaveBeenCalledTimes(2));

		mocks.fetchV3Document.mockClear();
		handlers.onError?.();
		await waitFor(() => expect(mocks.fetchV3Document).toHaveBeenCalledWith('gen-reopen'));
	});

	it('renders visual failure diagnostics from the polled document', async () => {
		window.history.replaceState({}, '', '/studio?generation_id=gen-visual-fail');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-visual-fail',
			stage: 'blueprint_ready',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: 'bp-visual-fail',
			execution_started: true,
			next_action: 'generation_running'
		});
		mocks.getV3GenerationBlueprint.mockResolvedValue({
			blueprint_id: 'bp-visual-fail',
			template_id: 'guided-concept-path',
			section_plan: [
				{
					id: 'orient',
					title: 'Orient',
					order: 0,
					learning_intent: 'Open the lesson',
					visual_required: true,
					components: []
				}
			],
			question_plan: [],
			resource_type: 'lesson',
			title: 'Test lesson',
			anchor: null,
			register_summary: '',
			support_summary: []
		});
		mocks.fetchV3Document.mockResolvedValue({
			kind: 'v3_booklet_pack',
			generation_id: 'gen-visual-fail',
			template_id: 'guided-concept-path',
			subject: 'Mathematics',
			status: 'streaming_preview',
			progress: {
				stage: 'writing',
				sections: { orient: 'failed' },
				updated_at: '2026-07-11T00:00:00Z'
			},
			section_diagnostics: [
				{
					section_id: 'orient',
					status: 'failed',
					renderable: false,
					missing_components: [],
					missing_visuals: ['required_visual'],
					warnings: ['provider timeout']
				}
			],
			sections: [{ section_id: 'orient', header: { title: 'Orient' } }],
			warnings: [],
			booklet_issues: []
		});

		render(StudioPage);
		await waitFor(() => expect(mocks.connectV3StudioGenerationStream).toHaveBeenCalled());
		await waitFor(() => expect(v3Studio.canvas[0]?.sectionStatus).toBe('failed'));
		expect(v3Studio.canvas[0]?.missingVisuals).toContain('required_visual');
		expect(v3Studio.canvas[0]?.diagnosticWarnings).toContain('provider timeout');
	});

	it('opens the current studio pack in Builder from the edit stage', async () => {
		v3Studio.stage = 'edit';
		v3Studio.generationId = 'gen-builder';
		v3Studio.bookletStatus = 'final_ready';
		v3Studio.activePack = {
			generation_id: 'gen-builder',
			blueprint_id: 'bp-1',
			template_id: 'guided-concept-path',
			subject: 'Mathematics',
			status: 'final_ready',
			sections: [{ section_id: 'intro', header: { title: 'Quadratic review' } }],
			warnings: [],
			section_diagnostics: [],
			booklet_issues: []
		};
		builderMocks.v3PackToBuilderDocument.mockReturnValue({
			id: 'lesson-doc-1',
			title: 'Quadratic review',
			subject: 'Mathematics',
			sections: [],
			blocks: {},
			media: {},
			version: 1,
			preset_id: 'blue-classroom',
			source: 'generated',
			created_at: '2026-06-22T00:00:00Z',
			updated_at: '2026-06-22T00:00:00Z'
		});
		builderMocks.createBuilderLesson.mockResolvedValue({
			id: 'builder-1',
			source_generation_id: 'gen-builder',
			source_type: 'v3_generation',
			title: 'Quadratic review',
			created_at: '2026-06-22T00:00:00Z',
			updated_at: '2026-06-22T00:00:00Z',
			document: { id: 'lesson-doc-1' }
		});
		builderMocks.saveDocument.mockResolvedValue(undefined);

		render(StudioPage);

		await fireEvent.click(await screen.findByRole('button', { name: 'Open in Builder' }));

		expect(builderMocks.v3PackToBuilderDocument).toHaveBeenCalledWith(
			expect.objectContaining({ generation_id: 'gen-builder' }),
			{ routeGenerationId: 'gen-builder' }
		);
		expect(builderMocks.createBuilderLesson).toHaveBeenCalledWith(
			expect.objectContaining({
				source_type: 'v3_generation',
				source_generation_id: 'gen-builder',
				title: 'Quadratic review'
			})
		);
		expect(builderMocks.saveDocument).toHaveBeenCalled();
		await waitFor(() => expect(navigationMocks.goto).toHaveBeenCalledWith('/builder/builder-1'));
	});

	it('shows review flags in the active studio edit surface', async () => {
		v3Studio.stage = 'edit';
		v3Studio.generationId = 'gen-issues';
		v3Studio.bookletStatus = 'draft_needs_review';
		v3Studio.activePack = {
			generation_id: 'gen-issues',
			blueprint_id: 'bp-1',
			template_id: 'guided-concept-path',
			subject: 'Mathematics',
			status: 'draft_needs_review',
			sections: [{ section_id: 'practice', header: { title: 'Practice' } }],
			warnings: [],
			section_diagnostics: [],
			booklet_issues: [{ message: 'Check worked example wording.', section_id: 'practice', category: 'clarity' }]
		};
		v3Studio.bookletIssues = v3Studio.activePack.booklet_issues;

		render(StudioPage);

		expect(await screen.findByText('Review flags')).toBeTruthy();
		expect(screen.getByText('Check worked example wording.')).toBeTruthy();
		expect(screen.getByText('practice - clarity')).toBeTruthy();
	});

	it('clears stale rendered booklet state before chunked regenerate resolves', async () => {
		window.history.replaceState({}, '', '/studio?generation_id=gen-regenerate');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-regenerate',
			stage: 'plan_ready',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [],
				question_plan: []
			},
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: false,
			next_action: 'approve_or_regenerate'
		});
		const regeneration = deferred<{
			generation_id: string;
			stage: 'plan_ready';
			structural_plan: {
				lesson_mode: string;
				lesson_intent: { goal: string; structure_rationale: string };
				anchor: { example: string; reuse_scope: string };
				sections: never[];
				question_plan: never[];
			};
			section_briefs: Record<string, never>;
			failed_sections: never[];
			blueprint_id: null;
			execution_started: false;
			next_action: 'approve_or_regenerate';
		}>();
		mocks.regenerateChunkedPlan.mockReturnValue(regeneration.promise);

		render(StudioPage);
		await waitFor(() => expect(mocks.getChunkedPlanStatus).toHaveBeenCalledWith('gen-regenerate'));

		v3Studio.canvas = [
			{
				id: 'stale',
				title: 'Stale section',
				teacher_labels: '',
				order: 0,
				sectionStatus: 'complete',
				stage2Preview: null,
				renderable: true,
				missingComponents: [],
				missingVisuals: [],
				diagnosticWarnings: [],
				components: [],
				visual: null,
				questions: [],
				mergedFields: { explanation: { body: 'old' } }
			}
		];
		v3Studio.draftPack = {
			generation_id: 'gen-regenerate',
			blueprint_id: 'bp-old',
			template_id: 'guided-concept-path',
			subject: 'Mathematics',
			status: 'draft_ready',
			sections: [{ section_id: 'stale' }],
			warnings: [],
			section_diagnostics: [],
			booklet_issues: []
		};
		v3Studio.finalPack = v3Studio.draftPack;
		v3Studio.activePack = v3Studio.draftPack;
		v3Studio.bookletIssues = [{ message: 'Old issue' }];

		await fireEvent.click(await screen.findByRole('button', { name: 'Regenerate' }));
		await fireEvent.click(await screen.findByRole('button', { name: 'Submit' }));

		expect(v3Studio.canvas).toEqual([]);
		expect(v3Studio.draftPack).toBeNull();
		expect(v3Studio.finalPack).toBeNull();
		expect(v3Studio.activePack).toBeNull();
		expect(v3Studio.bookletIssues).toEqual([]);
	});
});
