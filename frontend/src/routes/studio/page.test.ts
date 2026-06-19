// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	approveChunkedPlan: vi.fn(),
	adjustBlueprint: vi.fn(),
	connectV3ChunkedStream: vi.fn(() => vi.fn()),
	connectV3StudioGenerationStream: vi.fn(() => vi.fn()),
	getChunkedPlanStatus: vi.fn(),
	createV3SupplementBlueprint: vi.fn(),
	downloadV3GenerationPdf: vi.fn(),
	extractSignals: vi.fn(),
	fetchV3Document: vi.fn(),
	getV3GenerationBlueprint: vi.fn(),
	getV3SupplementOptions: vi.fn(),
	regenerateChunkedPlan: vi.fn(),
	retryChunkedSection: vi.fn(),
	startChunkedPlan: vi.fn(),
	startV3Generation: vi.fn()
}));

vi.mock('$lib/api/v3', () => ({
	approveChunkedPlan: mocks.approveChunkedPlan,
	adjustBlueprint: mocks.adjustBlueprint,
	connectV3ChunkedStream: mocks.connectV3ChunkedStream,
	connectV3StudioGenerationStream: mocks.connectV3StudioGenerationStream,
	getChunkedPlanStatus: mocks.getChunkedPlanStatus,
	createV3SupplementBlueprint: mocks.createV3SupplementBlueprint,
	downloadV3GenerationPdf: mocks.downloadV3GenerationPdf,
	extractSignals: mocks.extractSignals,
	fetchV3Document: mocks.fetchV3Document,
	getV3GenerationBlueprint: mocks.getV3GenerationBlueprint,
	getV3SupplementOptions: mocks.getV3SupplementOptions,
	regenerateChunkedPlan: mocks.regenerateChunkedPlan,
	retryChunkedSection: mocks.retryChunkedSection,
	startChunkedPlan: mocks.startChunkedPlan,
	startV3Generation: mocks.startV3Generation
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
vi.mock('$lib/components/studio/V3SupplementTray.svelte', async () => ({
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

describe('studio chunked URL resume', () => {
	beforeEach(() => {
		resetV3Studio();
		mocks.approveChunkedPlan.mockReset();
		mocks.connectV3ChunkedStream.mockReset();
		mocks.connectV3ChunkedStream.mockImplementation(() => vi.fn());
		mocks.connectV3StudioGenerationStream.mockReset();
		mocks.connectV3StudioGenerationStream.mockImplementation(() => vi.fn());
		mocks.getChunkedPlanStatus.mockReset();
		mocks.fetchV3Document.mockReset();
		mocks.getV3GenerationBlueprint.mockReset();
		window.history.replaceState({}, '', '/studio');
	});

	afterEach(() => {
		cleanup();
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
		expect(v3Studio.stage).toBe('chunked_review');
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
						id: 'orient',
						title: 'Orient',
						role: 'orient',
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
						id: 'orient',
						title: 'Orient',
						role: 'orient',
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
		expect(v3Studio.stage).toBe('planning');
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

		await waitFor(() => expect(mocks.approveChunkedPlan).toHaveBeenCalledWith('gen-approve'));
		expect(v3Studio.stage).toBe('planning');
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
		expect(v3Studio.stage).toBe('planning');
		expect(mocks.fetchV3Document).not.toHaveBeenCalled();
	});

	it('does not connect the stream when approve returns assembly_blocked', async () => {
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
			failed_sections: ['orient'],
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
			expect(mocks.approveChunkedPlan).toHaveBeenCalledWith('gen-approve-blocked')
		);
		expect(v3Studio.stage).toBe('chunked_blocked');
		expect(mocks.connectV3StudioGenerationStream).not.toHaveBeenCalled();
	});

	it('switches from chunked SSE to generation SSE after stage2 completes', async () => {
		vi.useFakeTimers();
		window.history.replaceState({}, '', '/studio?generation_id=gen-switch');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-switch',
			stage: 'plan_ready',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [{ id: 'orient', title: 'Orient', role: 'orient', visual_required: false, transition_note: null, components: [] }],
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
				sections: [{ id: 'orient', title: 'Orient', role: 'orient', visual_required: false, transition_note: null, components: [] }],
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

		expect(mocks.connectV3StudioGenerationStream).not.toHaveBeenCalled();
		await vi.advanceTimersByTimeAsync(1499);
		expect(mocks.connectV3StudioGenerationStream).not.toHaveBeenCalled();
		await vi.advanceTimersByTimeAsync(1);
		await waitFor(() =>
			expect(mocks.connectV3StudioGenerationStream).toHaveBeenCalledWith(
				'gen-switch',
				expect.any(Object)
			)
		);
		expect(disconnectChunked).toHaveBeenCalled();
		vi.useRealTimers();
	});

	it('stays blocked and skips generation SSE when chunked stage2 completes with failures', async () => {
		window.history.replaceState({}, '', '/studio?generation_id=gen-failed');
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-failed',
			stage: 'plan_ready',
			structural_plan: {
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'Reuse' },
				sections: [{ id: 'orient', title: 'Orient', role: 'orient', visual_required: false, transition_note: null, components: [] }],
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
				sections: [{ id: 'orient', title: 'Orient', role: 'orient', visual_required: false, transition_note: null, components: [] }],
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
		handlers.onStage2Complete?.(['orient']);
		expect(v3Studio.stage).toBe('chunked_blocked');
		expect(disconnectChunked).toHaveBeenCalled();
		expect(mocks.connectV3StudioGenerationStream).not.toHaveBeenCalled();

		handlers.onAssemblyBlocked?.(['orient']);
		expect(v3Studio.stage).toBe('chunked_blocked');
		expect(mocks.connectV3StudioGenerationStream).not.toHaveBeenCalled();
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
					{ id: 'orient', title: 'Orient', role: 'orient', visual_required: false, transition_note: null, components: [] },
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
					{ id: 'orient', title: 'Orient', role: 'orient', visual_required: false, transition_note: null, components: [] },
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
			onSectionDone?: (sectionId: string) => void;
			onSectionFailed?: (sectionId: string, errors: string[]) => void;
		};
		const orient = await screen.findByText('orient');
		const model = await screen.findByText('model');

		handlers.onSectionStart?.('orient');
		await waitFor(() => expect(orient.className).toContain('active'));

		handlers.onSectionDone?.('orient');
		await waitFor(() => expect(orient.className).toContain('done'));

		handlers.onSectionFailed?.('model', ['boom']);
		await waitFor(() => expect(model.className).toContain('failed'));
	});

	it('fails soft when generation_id cannot be resumed', async () => {
		window.history.replaceState({}, '', '/studio?generation_id=gen-missing');
		mocks.getChunkedPlanStatus.mockRejectedValue(new Error('404'));

		render(StudioPage);

		await waitFor(() => expect(mocks.getChunkedPlanStatus).toHaveBeenCalledWith('gen-missing'));
		await waitFor(() => expect(v3Studio.stage).toBe('input'));
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
						id: 'orient',
						title: 'Orient',
						role: 'orient',
						visual_required: false,
						transition_note: null,
						components: []
					}
				],
				question_plan: []
			},
			section_briefs: { orient: null },
			failed_sections: ['orient'],
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
						id: 'orient',
						title: 'Orient',
						role: 'orient',
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
		expect(v3Studio.stage).toBe('chunked_blocked');

		await fireEvent.click(await screen.findByRole('button', { name: /retry orient/i }));
		await waitFor(() =>
			expect(mocks.retryChunkedSection).toHaveBeenCalledWith({
				generation_id: 'gen-blocked',
				section_id: 'orient'
			})
		);
		await waitFor(() => expect(v3Studio.stage).toBe('planning'));
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
		expect(v3Studio.stage).toBe('generating');
	});
});
