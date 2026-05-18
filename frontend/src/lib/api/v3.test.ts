import { beforeEach, describe, expect, it, vi } from 'vitest';

const { fetchEventSourceMock, capturedOptions, apiFetchMock } = vi.hoisted(() => {
	let options: Record<string, unknown> | null = null;
	return {
		fetchEventSourceMock: vi.fn((_url: string, init: Record<string, unknown>) => {
			options = init;
		}),
		apiFetchMock: vi.fn(),
		capturedOptions: {
			get current() {
				return options;
			}
		}
	};
});

vi.mock('@microsoft/fetch-event-source', () => ({
	fetchEventSource: fetchEventSourceMock
}));

vi.mock('$lib/api/client', () => ({
	apiFetch: apiFetchMock,
	buildApiUrl: (path: string) => path
}));

vi.mock('$lib/api/errors', () => ({
	ensureOk: async (response: Response, message: string) => {
		if (!response.ok) throw new Error(message);
	}
}));

vi.mock('$lib/stores/auth', () => ({
	authToken: {
		subscribe(callback: (value: string | null) => void) {
			callback(null);
			return () => {};
		}
	}
}));

import {
	approveChunkedPlan,
	connectV3ChunkedStream,
	connectV3StudioGenerationStream,
	fetchV3Document,
	generateBlueprint,
	getChunkedPlanStatus,
	getV3GenerationBlueprint,
	getV3GenerationDetail,
	getV3Generations
} from './v3';

describe('connectV3StudioGenerationStream', () => {
	beforeEach(() => {
		fetchEventSourceMock.mockClear();
		apiFetchMock.mockReset();
	});

	function buildSignals() {
		return {
			topic: 'Fractions',
			subtopic: 'Equivalent fractions',
			prior_knowledge: ['equal sharing'],
			learner_needs: [],
			teacher_goal: 'Build understanding',
			inferred_resource_type: 'worksheet',
			confidence: 'medium' as const,
			missing_signals: []
		};
	}

	function buildForm() {
		return {
			grade_level: 'Grade 5',
			subject: 'Mathematics',
			duration_minutes: 45,
			topic: 'Equivalent fractions',
			subtopics: ['pizza model'],
			prior_knowledge: 'Equal sharing',
			lesson_mode: 'first_exposure' as const,
			lesson_mode_other: '',
			intended_outcome: 'understand' as const,
			intended_outcome_other: '',
			learner_level: 'on_grade' as const,
			reading_level: 'on_grade' as const,
			language_support: 'none' as const,
			prior_knowledge_level: 'some_background' as const,
			support_needs: ['visuals'],
			learning_preferences: [],
			free_text: ''
		};
	}

	function buildPreview() {
		return {
			blueprint_id: 'bp-123',
			resource_type: 'worksheet',
			title: 'Equivalent Fractions',
			template_id: 'guided-concept-path',
			lenses: [],
			anchor: {
				label: 'Pizza anchor',
				facts: {},
				correct_result: null,
				reuse_scope: 'whole lesson'
			},
			section_plan: [],
			question_plan: [],
			register_summary: 'simple',
			support_summary: []
		};
	}

	it('routes new pack events to dedicated handlers', () => {
		const onDraftPackReady = vi.fn();
		const onFinalPackReady = vi.fn();
		const onDraftStatusUpdated = vi.fn();
		const onSectionWriterFailed = vi.fn();

		connectV3StudioGenerationStream('gen-1', {
			onDraftPackReady,
			onFinalPackReady,
			onDraftStatusUpdated,
			onSectionWriterFailed
		});

		const onmessage = capturedOptions.current?.onmessage as
			| ((msg: { event?: string; data?: string }) => void)
			| undefined;
		expect(onmessage).toBeTypeOf('function');

		onmessage?.({ event: 'draft_pack_ready', data: '{"pack":{"sections":[]}}' });
		onmessage?.({ event: 'final_pack_ready', data: '{"pack":{"sections":[]}}' });
		onmessage?.({ event: 'draft_status_updated', data: '{"booklet_status":"draft_ready"}' });
		onmessage?.({
			event: 'section_writer_failed',
			data: '{"section_id":"sec-1","errors":["boom"],"warnings":[]}'
		});

		expect(onDraftPackReady).toHaveBeenCalledTimes(1);
		expect(onFinalPackReady).toHaveBeenCalledTimes(1);
		expect(onDraftStatusUpdated).toHaveBeenCalledTimes(1);
		expect(onSectionWriterFailed).toHaveBeenCalledTimes(1);
	});

	it('fetches persisted V3 document payload from API', async () => {
		apiFetchMock.mockResolvedValue({
			ok: true,
			json: async () => ({
				kind: 'v3_booklet_pack',
				sections: [{ section_id: 's-1' }]
			})
		});

		const doc = await fetchV3Document('gen-1');
		expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/v3/generations/gen-1/document', {
			method: 'GET',
			headers: { 'Content-Type': 'application/json' }
		});
		expect(doc.sections).toHaveLength(1);
	});

	it('loads V3 generation history from the V3 endpoint', async () => {
		apiFetchMock.mockResolvedValue({
			ok: true,
			json: async () => [{ id: 'gen-1', status: 'completed' }]
		});

		const rows = await getV3Generations();
		expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/v3/generations?limit=20&offset=0', {
			method: 'GET',
			headers: { 'Content-Type': 'application/json' }
		});
		expect(rows).toHaveLength(1);
	});

	it('loads V3 generation detail from the V3 endpoint', async () => {
		apiFetchMock.mockResolvedValue({
			ok: true,
			json: async () => ({ id: 'gen-1', status: 'completed' })
		});

		const row = await getV3GenerationDetail('gen-1');
		expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/v3/generations/gen-1', {
			method: 'GET',
			headers: { 'Content-Type': 'application/json' }
		});
		expect(row.id).toBe('gen-1');
	});

	it('sends architect_mode=standard in body when specified', async () => {
		apiFetchMock.mockResolvedValue({
			ok: true,
			json: async () => buildPreview()
		});

		await generateBlueprint({
			signals: buildSignals(),
			form: buildForm(),
			clarification_answers: [],
			architect_mode: 'standard'
		});

		const payload = JSON.parse(apiFetchMock.mock.calls[0][1].body as string);
		expect(payload.architect_mode).toBe('standard');
	});

	it('sends architect_mode=chunked in body when specified', async () => {
		apiFetchMock.mockResolvedValue({
			ok: true,
			json: async () => buildPreview()
		});

		await generateBlueprint({
			signals: buildSignals(),
			form: buildForm(),
			clarification_answers: [],
			architect_mode: 'chunked'
		});

		const payload = JSON.parse(apiFetchMock.mock.calls[0][1].body as string);
		expect(payload.architect_mode).toBe('chunked');
	});

	it('does NOT include architect_mode key in body when omitted', async () => {
		apiFetchMock.mockResolvedValue({
			ok: true,
			json: async () => buildPreview()
		});

		await generateBlueprint({
			signals: buildSignals(),
			form: buildForm(),
			clarification_answers: []
		});

		const payload = JSON.parse(apiFetchMock.mock.calls[0][1].body as string);
		expect(payload.architect_mode).toBeUndefined();
	});

	it('always posts to /api/v1/v3/blueprint', async () => {
		apiFetchMock.mockResolvedValue({
			ok: true,
			json: async () => buildPreview()
		});

		await generateBlueprint({
			signals: buildSignals(),
			form: buildForm(),
			clarification_answers: [],
			architect_mode: 'chunked'
		});

		expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/v3/blueprint', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: expect.any(String)
		});
	});

	it('returns BlueprintPreviewDTO from response', async () => {
		apiFetchMock.mockResolvedValue({
			ok: true,
			json: async () => buildPreview()
		});

		const result = await generateBlueprint({
			signals: buildSignals(),
			form: buildForm(),
			clarification_answers: [],
			architect_mode: 'chunked'
		});

		expect(result.blueprint_id).toBe('bp-123');
		expect(result.title).toBe('Equivalent Fractions');
	});

	it('routes chunked stage events to handlers', () => {
		const onPlanReady = vi.fn();
		const onStage2SectionFailed = vi.fn();
		const onGenerationStarting = vi.fn();

		connectV3StudioGenerationStream('gen-1', {
			onPlanReady,
			onStage2SectionFailed,
			onGenerationStarting
		});

		const onmessage = capturedOptions.current?.onmessage as
			| ((msg: { event?: string; data?: string }) => void)
			| undefined;
		expect(onmessage).toBeTypeOf('function');

		onmessage?.({ event: 'plan_ready', data: '{"plan":{"sections":[]}}' });
		onmessage?.({ event: 'stage2_section_failed', data: '{"section_id":"model","errors":["bad"]}' });
		onmessage?.({ event: 'generation_starting', data: '{"generation_id":"gen-1"}' });

		expect(onPlanReady).toHaveBeenCalledTimes(1);
		expect(onStage2SectionFailed).toHaveBeenCalledTimes(1);
		expect(onGenerationStarting).toHaveBeenCalledTimes(1);
	});

	it('connects chunked planning SSE and dispatches planning events', () => {
		const onSectionStart = vi.fn();
		const onSectionRetry = vi.fn();
		const onSectionDone = vi.fn();
		const onSectionFailed = vi.fn();
		const onStage2Complete = vi.fn();
		const onAssemblyBlocked = vi.fn();
		const onError = vi.fn();

		connectV3ChunkedStream('gen-1', {
			onSectionStart,
			onSectionRetry,
			onSectionDone,
			onSectionFailed,
			onStage2Complete,
			onAssemblyBlocked,
			onError
		});

		expect(fetchEventSourceMock).toHaveBeenCalledWith(
			'/api/v1/v3/chunked/gen-1/events',
			expect.any(Object)
		);

		const onmessage = capturedOptions.current?.onmessage as
			| ((msg: { event?: string; data?: string }) => void)
			| undefined;
		expect(onmessage).toBeTypeOf('function');

		onmessage?.({ event: 'stage2_section_start', data: '{"section_id":"orient"}' });
		onmessage?.({ event: 'stage2_section_retry', data: '{"section_id":"orient","attempt":3}' });
		onmessage?.({ event: 'stage2_section_done', data: '{"section_id":"orient"}' });
		onmessage?.({
			event: 'stage2_section_failed',
			data: '{"section_id":"model","errors":["bad"]}'
		});
		onmessage?.({ event: 'stage2_complete', data: '{"failed_sections":["model"]}' });
		onmessage?.({ event: 'assembly_blocked', data: '{"failed_sections":["model"]}' });
		onmessage?.({ event: 'generation_warning', data: '{"message":"warning"}' });

		expect(onSectionStart).toHaveBeenCalledWith('orient');
		expect(onSectionRetry).toHaveBeenCalledWith('orient', 3);
		expect(onSectionDone).toHaveBeenCalledWith('orient');
		expect(onSectionFailed).toHaveBeenCalledWith('model', ['bad']);
		expect(onStage2Complete).toHaveBeenCalledWith(['model']);
		expect(onAssemblyBlocked).toHaveBeenCalledWith(['model']);
		expect(onError).toHaveBeenCalledWith('warning');
	});

	it('calls chunked lifecycle endpoints', async () => {
		apiFetchMock.mockResolvedValue({
			ok: true,
			json: async () => ({ generation_id: 'gen-1', stage: 'plan_ready' })
		});

		await approveChunkedPlan('gen-1');
		expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/v3/chunked/gen-1/approve', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' }
		});

		await getChunkedPlanStatus('gen-1');
		expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/v3/chunked/gen-1/status', {
			method: 'GET',
			headers: { 'Content-Type': 'application/json' }
		});
	});

	it('loads generation blueprint preview', async () => {
		apiFetchMock.mockResolvedValue({
			ok: true,
			json: async () => ({ blueprint_id: 'bp-1', title: 'Plan' })
		});
		const preview = await getV3GenerationBlueprint('gen-1');
		expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/v3/generations/gen-1/blueprint', {
			method: 'GET',
			headers: { 'Content-Type': 'application/json' }
		});
		expect(preview.blueprint_id).toBe('bp-1');
	});

	describe('narrowTopic', () => {
		it('posts to /api/v1/v3/narrow and returns candidates', async () => {
			apiFetchMock.mockResolvedValue({
				ok: true,
				json: async () => ({
					candidates: [
						{
							id: 'seed-dispersal',
							title: 'Seed dispersal',
							description: 'How plants spread seeds.'
						},
						{
							id: 'pollination',
							title: 'Pollination',
							description: 'Role of insects.'
						}
					]
				})
			});

			const { narrowTopic } = await import('./v3');
			const result = await narrowTopic({
				topic: 'Reproduction in plants',
				grade_level: 'Grade 6',
				subject: 'Biology'
			});

			expect(apiFetchMock).toHaveBeenCalledWith(
				'/api/v1/v3/narrow',
				expect.objectContaining({ method: 'POST' })
			);
			const body = JSON.parse(apiFetchMock.mock.calls[0][1].body);
			expect(body.topic).toBe('Reproduction in plants');
			expect(result).toHaveLength(2);
			expect(result[0].title).toBe('Seed dispersal');
		});

		it('returns empty array when response has no candidates', async () => {
			apiFetchMock.mockResolvedValue({
				ok: true,
				json: async () => ({})
			});
			const { narrowTopic } = await import('./v3');
			const result = await narrowTopic({
				topic: 'Photosynthesis',
				grade_level: 'Grade 5',
				subject: 'Science'
			});
			expect(result).toEqual([]);
		});
	});
});
