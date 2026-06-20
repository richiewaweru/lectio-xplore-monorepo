<script lang="ts">
	import { browser } from '$app/environment';
	import { onDestroy, onMount } from 'svelte';

	import V3InputSurface from '$lib/components/studio/V3InputSurface.svelte';
	import V3PlanningState from '$lib/components/studio/V3PlanningState.svelte';
	import V3PlanPreview from '$lib/components/studio/V3PlanPreview.svelte';
	import V3PlanActions from '$lib/components/studio/V3PlanActions.svelte';
	import V3Canvas from '$lib/components/studio/V3Canvas.svelte';
	import V3BookletPackView from '$lib/components/studio/V3BookletPackView.svelte';

	import {
		approveChunkedPlan,
		connectV3ChunkedStream,
		connectV3StudioGenerationStream,
		downloadV3GenerationPdf,
		extractSignals,
		fetchV3Document,
		getChunkedPlanStatus,
		getV3GenerationBlueprint,
		regenerateChunkedPlan,
		retryChunkedSection,
		startChunkedPlan
	} from '$lib/api/v3';
	import { isApiError } from '$lib/api/errors';
	import { resetV3Studio, v3Studio } from '$lib/stores/v3-studio.svelte';
	import {
		applyComponentPatchedToCanvas,
		applyComponentReadyToCanvas,
		applySectionWriterFailedToCanvas
	} from '$lib/studio/v3-stream-state';
	import { buildCanvasSkeleton, mergeDiagramFrame, mergePracticeProblem } from '$lib/studio/v3-canvas';
	import { getBookletExportPolicy, isBookletStatus } from '$lib/studio/v3-booklet';
	import { coerceV3DocumentToPack } from '$lib/studio/v3-document';
	import { mapPackSectionsToCanvas } from '$lib/studio/v3-print-canvas';
	import type { BookletStatus, V3ChunkedPlanState, V3DraftPack, V3InputForm } from '$lib/types/v3';

	let pdfLoading = $state(false);
	let pdfError = $state<string | null>(null);
	let pdfConfirming = $state(false);
	let pdfOpen = $state(false);
	let schoolName = $state('');
	let teacherName = $state('');
	let exportDate = $state('');
	let includeAnswers = $state(true);
	const currentExportPolicy = $derived(getBookletExportPolicy(v3Studio.bookletStatus));
	let stage2Progress = $state<{
		completed: string[];
		failed: string[];
		active: string | null;
	}>({ completed: [], failed: [], active: null });
	let disconnectChunkedStream: (() => void) | null = null;

	function disconnectActiveChunkedStream(): void {
		disconnectChunkedStream?.();
		disconnectChunkedStream = null;
	}

	function syncStage2Progress(state: V3ChunkedPlanState | null): void {
		const sections = state?.structural_plan?.sections ?? [];
		const sectionBriefs = state?.section_briefs ?? {};
		const failedSections = new Set(state?.failed_sections ?? []);
		stage2Progress = {
			completed: sections
				.map((section) => section.id)
				.filter((sectionId) => {
					const brief = sectionBriefs[sectionId];
					return typeof brief === 'object' && brief !== null && !failedSections.has(sectionId);
				}),
			failed: Array.from(failedSections),
			active: null
		};
	}

	function handleStartOver(): void {
		disconnectActiveChunkedStream();
		resetV3Studio();
	}

	function setGenerationQuery(generationId: string | null): void {
		if (!browser) return;
		const url = new URL(window.location.href);
		if (generationId && generationId.trim()) {
			url.searchParams.set('generation_id', generationId);
		} else {
			url.searchParams.delete('generation_id');
		}
		const next = `${url.pathname}${url.search}${url.hash}`;
		if (next !== `${window.location.pathname}${window.location.search}${window.location.hash}`) {
			window.history.replaceState(window.history.state, '', next);
		}
	}

	function hydrateChunkedSectionState(state: V3ChunkedPlanState): void {
		const sectionStatus: Record<string, 'pending' | 'running' | 'retrying' | 'done' | 'failed'> = {};
		const sectionErrors: Record<string, string[]> = {};
		const failedSections = new Set(state.failed_sections);
		const sectionBriefs = state.section_briefs ?? {};
		const sections = state.structural_plan?.sections ?? [];

		for (const section of sections) {
			const sectionId = section.id;
			const persisted = sectionBriefs[sectionId];
			if (failedSections.has(sectionId)) {
				sectionStatus[sectionId] = 'failed';
				sectionErrors[sectionId] = ['Section failed in prior attempt.'];
			} else if (persisted && typeof persisted === 'object') {
				sectionStatus[sectionId] = 'done';
				sectionErrors[sectionId] = [];
			} else {
				sectionStatus[sectionId] = 'pending';
				sectionErrors[sectionId] = [];
			}
		}
		v3Studio.chunkedSectionStatus = sectionStatus;
		v3Studio.chunkedSectionErrors = sectionErrors;
	}

	async function applyChunkedState(
		state: V3ChunkedPlanState,
		{ resume = false }: { resume?: boolean } = {}
	): Promise<void> {
		let resolved = state;
		if (resume && state.stage === 'stage2_running') {
			try {
				resolved = await approveChunkedPlan(state.generation_id);
			} catch {
				resolved = state;
			}
		}

		v3Studio.chunkedState = resolved;
		v3Studio.generationId = resolved.generation_id;
		hydrateChunkedSectionState(resolved);
		syncStage2Progress(resolved);

		if (resolved.stage === 'plan_ready') {
			disconnectActiveChunkedStream();
			v3Studio.stage = 'skeleton';
			return;
		}
		if (resolved.stage === 'assembly_blocked') {
			disconnectActiveChunkedStream();
			v3Studio.stage = 'skeleton';
			return;
		}
		if (resolved.stage === 'stage2_running') {
			v3Studio.stage = 'fill';
			connectChunkedStage2Stream(resolved.generation_id);
			return;
		}
		if (resolved.stage === 'blueprint_ready') {
			disconnectActiveChunkedStream();
			v3Studio.stage = 'fill';
			connectGenerationStream(resolved.generation_id);
			try {
				const preview = await getV3GenerationBlueprint(resolved.generation_id);
				v3Studio.blueprint = preview;
				if (v3Studio.canvas.length === 0) {
					v3Studio.canvas = buildCanvasSkeleton(preview);
				}
			} catch {
				// Ignore preview recovery failures; stream and document hydration continue.
			}
			return;
		}
		if (resolved.stage === 'complete') {
			disconnectActiveChunkedStream();
			v3Studio.stage = 'edit';
			try {
				const preview = await getV3GenerationBlueprint(resolved.generation_id);
				v3Studio.blueprint = preview;
			} catch {
				// Ignore missing preview and continue with persisted document hydration.
			}
			await hydrateFromDocument(resolved.generation_id);
		}
	}

	async function resumeChunkedFromQuery(): Promise<void> {
		if (!browser) return;
		const generationId = new URL(window.location.href).searchParams.get('generation_id');
		if (!generationId) return;
		v3Studio.error = null;
		try {
			const state = await getChunkedPlanStatus(generationId);
			await applyChunkedState(state, { resume: true });
		} catch {
			resetV3Studio();
			v3Studio.error = 'Could not resume that chunked session. Start a new lesson plan.';
		}
	}

	function friendly(err: unknown): string {
		if (isApiError(err)) return err.detail;
		if (err instanceof Error) return err.message;
		return 'Something went wrong. Try again.';
	}

	function parsePack(payload: unknown): V3DraftPack | null {
		if (typeof payload !== 'object' || payload === null) return null;
		const candidate = (payload as { pack?: unknown }).pack;
		if (typeof candidate !== 'object' || candidate === null) return null;
		return candidate as V3DraftPack;
	}

	function statusFromPayload(payload: Record<string, unknown>, fallback: BookletStatus): BookletStatus {
		return isBookletStatus(payload.booklet_status) ? payload.booklet_status : fallback;
	}

	async function hydrateFromDocument(generationId: string): Promise<boolean> {
		try {
			const document = await fetchV3Document(generationId);
			const pack = coerceV3DocumentToPack(generationId, document, {
				templateId: v3Studio.blueprint?.template_id ?? 'guided-concept-path'
			});
			if (!pack) return false;
			v3Studio.draftPack = pack;
			v3Studio.activePack = pack;
			if (pack.status === 'final_ready' || pack.status === 'final_with_warnings') {
				v3Studio.finalPack = pack;
			}
			v3Studio.bookletStatus = pack.status;
			v3Studio.bookletIssues = pack.booklet_issues;
			v3Studio.canvas = mapPackSectionsToCanvas(pack.sections);
			if (pack.status !== 'streaming_preview') {
				v3Studio.coherenceHint = null;
				v3Studio.stage = 'edit';
			}
			return true;
		} catch {
			return false;
		}
	}

	async function refreshChunkedStatus(generationId: string): Promise<void> {
		try {
			const state = await getChunkedPlanStatus(generationId);
			await applyChunkedState(state);
		} catch {
			// Keep current UI state if status refresh fails.
		}
	}

	async function handleInputSubmit(form: V3InputForm) {
		v3Studio.error = null;
		v3Studio.form = form;
		v3Studio.stage = 'fill';
		try {
			v3Studio.signals = await extractSignals(form);
			const chunkedState = await startChunkedPlan({
				signals: v3Studio.signals,
				form
			});
			await applyChunkedState(chunkedState);
		} catch (err) {
			v3Studio.stage = 'intent';
			v3Studio.error = friendly(err);
		}
	}

	function connectChunkedStage2Stream(generationId: string): void {
		disconnectActiveChunkedStream();
		disconnectChunkedStream = connectV3ChunkedStream(generationId, {
			onSectionStart(sectionId) {
				stage2Progress = {
					...stage2Progress,
					active: sectionId
				};
				v3Studio.chunkedSectionStatus = {
					...v3Studio.chunkedSectionStatus,
					[sectionId]: 'running'
				};
			},
			onSectionDone(sectionId) {
				stage2Progress = {
					completed: Array.from(new Set([...stage2Progress.completed, sectionId])),
					failed: stage2Progress.failed.filter((id) => id !== sectionId),
					active: null
				};
				v3Studio.chunkedSectionStatus = {
					...v3Studio.chunkedSectionStatus,
					[sectionId]: 'done'
				};
				v3Studio.chunkedSectionErrors = {
					...v3Studio.chunkedSectionErrors,
					[sectionId]: []
				};
			},
			onSectionRetry(sectionId) {
				stage2Progress = {
					...stage2Progress,
					active: sectionId
				};
				v3Studio.chunkedSectionStatus = {
					...v3Studio.chunkedSectionStatus,
					[sectionId]: 'retrying'
				};
			},
			onSectionFailed(sectionId, errors) {
				console.warn('[chunked] section failed', sectionId, errors);
				stage2Progress = {
					completed: stage2Progress.completed.filter((id) => id !== sectionId),
					failed: Array.from(new Set([...stage2Progress.failed, sectionId])),
					active: null
				};
				v3Studio.chunkedSectionStatus = {
					...v3Studio.chunkedSectionStatus,
					[sectionId]: 'failed'
				};
				v3Studio.chunkedSectionErrors = {
					...v3Studio.chunkedSectionErrors,
					[sectionId]: errors
				};
			},
			onStage2Complete(failedSections) {
				if (v3Studio.chunkedState) {
					v3Studio.chunkedState = {
						...v3Studio.chunkedState,
						stage: failedSections.length > 0 ? 'assembly_blocked' : 'stage2_complete',
						failed_sections: failedSections
					};
				}
				stage2Progress = {
					completed: stage2Progress.completed,
					failed: failedSections,
					active: null
				};
				if (failedSections.length > 0) {
					v3Studio.stage = 'skeleton';
					disconnectActiveChunkedStream();
					return;
				}
				setTimeout(() => {
					disconnectActiveChunkedStream();
					connectGenerationStream(generationId);
				}, 1500);
			},
			onAssemblyBlocked(failedSections) {
				console.warn('[chunked] assembly blocked', failedSections);
				if (v3Studio.chunkedState) {
					v3Studio.chunkedState = {
						...v3Studio.chunkedState,
						stage: 'assembly_blocked',
						failed_sections: failedSections
					};
				}
				stage2Progress = {
					completed: stage2Progress.completed,
					failed: failedSections,
					active: null
				};
				v3Studio.stage = 'skeleton';
				disconnectActiveChunkedStream();
			},
			onError(msg) {
				console.error('[chunked stream error]', msg);
			}
		});
	}

	function connectGenerationStream(generationId: string) {
		disconnectActiveChunkedStream();
		v3Studio.streamCancel?.();
		v3Studio.streamCancel = connectV3StudioGenerationStream(generationId, {
			onCoherenceReviewStarted: () => {
				v3Studio.stage = 'fill';
			},
			onCoherenceReportReady: (data) => {
				const blocking = typeof data.blocking_count === 'number' ? data.blocking_count : 0;
				v3Studio.coherenceHint =
					blocking > 0
						? `Consistency review finished with ${blocking} blocking issue(s) flagged.`
						: 'Consistency review finished.';
			},
			onDraftPackReady: (data) => {
				const pack = parsePack(data);
				if (!pack) return;
				const status = statusFromPayload(data, pack.status);
				v3Studio.draftPack = pack;
				v3Studio.activePack = pack;
				v3Studio.bookletStatus = status;
				v3Studio.bookletIssues = Array.isArray(pack.booklet_issues) ? pack.booklet_issues : [];
			},
			onFinalPackReady: (data) => {
				const pack = parsePack(data);
				if (!pack) return;
				const status = statusFromPayload(data, pack.status);
				v3Studio.finalPack = pack;
				v3Studio.activePack = pack;
				v3Studio.bookletStatus = status;
				v3Studio.bookletIssues = Array.isArray(pack.booklet_issues) ? pack.booklet_issues : [];
			},
			onDraftStatusUpdated: (data) => {
				const status = statusFromPayload(data, v3Studio.bookletStatus);
				const pack = parsePack(data);
				if (pack) {
					v3Studio.draftPack = pack;
					v3Studio.activePack = pack;
					v3Studio.bookletIssues = Array.isArray(pack.booklet_issues) ? pack.booklet_issues : [];
				}
				v3Studio.bookletStatus = status;
			},
			onResourceFinalised: () => {
				const gid = v3Studio.generationId;
				if (gid) {
					void hydrateFromDocument(gid);
				}
				v3Studio.streamCancel?.();
				v3Studio.streamCancel = null;
				v3Studio.stage = 'edit';
			},
			onComponentReady: (data) => {
				const next = applyComponentReadyToCanvas(v3Studio.canvas, data);
				v3Studio.canvas = next.canvas;
				if (next.warning) {
					console.warn('component_ready warning', data);
					v3Studio.error = next.warning;
				}
			},
			onSectionWriterFailed: (data) => {
				const next = applySectionWriterFailedToCanvas(v3Studio.canvas, data);
				v3Studio.canvas = next.canvas;
				if (next.warning) {
					v3Studio.error = next.warning;
				}
			},
			onVisualReady: (data) => {
				const sid = String(data.attaches_to ?? '');
				const url = typeof data.image_url === 'string' ? data.image_url : null;
				const fi =
					data.frame_index === undefined ? null : (data.frame_index as number | null);
				if (!sid) return;
				v3Studio.canvas = v3Studio.canvas.map((s) => {
					if (s.id !== sid) return s;
					const mergedFields = mergeDiagramFrame(s.mergedFields, {
						image_url: url,
						frame_index: fi
					});
					const visual = s.visual
						? {
								...s.visual,
								status: 'ready' as const,
								image_url: url ?? s.visual.image_url,
								frame_index: fi ?? s.visual.frame_index
							}
						: null;
					return { ...s, mergedFields, visual };
				});
			},
			onQuestionReady: (data) => {
				const sid = String(data.section_id ?? '');
				const qid = String(data.question_id ?? '');
				const diff = String(data.difficulty ?? 'warm');
				const raw = data.data;
				const pdata =
					typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {};
				if (!sid || !qid) return;
				v3Studio.canvas = v3Studio.canvas.map((s) =>
					s.id !== sid
						? s
						: {
								...s,
								mergedFields: mergePracticeProblem(s.mergedFields, qid, diff, pdata),
								questions: s.questions.map((q) =>
									q.id === qid ? { ...q, status: 'ready' as const, data: pdata } : q
								)
							}
				);
			},
			onComponentPatched: (data) => {
				const next = applyComponentPatchedToCanvas(v3Studio.canvas, data);
				v3Studio.canvas = next.canvas;
				if (next.warning) {
					console.warn('component_patched warning', data);
					v3Studio.error = next.warning;
				}
			},
			onPlanReady: (data) => {
				const plan = data.plan;
				if (typeof plan !== 'object' || plan === null || !v3Studio.generationId) return;
				v3Studio.chunkedState = {
					generation_id: v3Studio.generationId,
					stage: 'plan_ready',
					structural_plan: plan as any,
					section_briefs: {},
					failed_sections: [],
					blueprint_id: null,
					execution_started: false,
					next_action: 'approve_or_regenerate'
				};
				v3Studio.stage = 'skeleton';
			},
			onStage2SectionStart: (data) => {
				const sectionId = String(data.section_id ?? '');
				if (!sectionId) return;
				v3Studio.chunkedSectionStatus = {
					...v3Studio.chunkedSectionStatus,
					[sectionId]: 'running'
				};
			},
			onStage2SectionRetry: (data) => {
				const sectionId = String(data.section_id ?? '');
				if (!sectionId) return;
				v3Studio.chunkedSectionStatus = {
					...v3Studio.chunkedSectionStatus,
					[sectionId]: 'retrying'
				};
			},
			onStage2SectionDone: (data) => {
				const sectionId = String(data.section_id ?? '');
				if (!sectionId) return;
				v3Studio.chunkedSectionStatus = {
					...v3Studio.chunkedSectionStatus,
					[sectionId]: 'done'
				};
				v3Studio.chunkedSectionErrors = {
					...v3Studio.chunkedSectionErrors,
					[sectionId]: []
				};
			},
			onStage2SectionFailed: (data) => {
				const sectionId = String(data.section_id ?? '');
				if (!sectionId) return;
				const errors = Array.isArray(data.errors)
					? data.errors.filter((item): item is string => typeof item === 'string')
					: [];
				v3Studio.chunkedSectionStatus = {
					...v3Studio.chunkedSectionStatus,
					[sectionId]: 'failed'
				};
				v3Studio.chunkedSectionErrors = {
					...v3Studio.chunkedSectionErrors,
					[sectionId]: errors
				};
			},
			onStage2Complete: (data) => {
				const failedSections = Array.isArray(data.failed_sections)
					? data.failed_sections.filter((item): item is string => typeof item === 'string')
					: [];
				if (v3Studio.chunkedState) {
					v3Studio.chunkedState = {
						...v3Studio.chunkedState,
						stage: failedSections.length ? 'assembly_blocked' : 'stage2_complete',
						failed_sections: failedSections
					};
				}
				if (failedSections.length) {
					v3Studio.stage = 'skeleton';
				}
			},
			onGenerationStarting: () => {
				const gid = v3Studio.generationId;
				if (!gid) return;
				v3Studio.stage = 'fill';
				void (async () => {
					try {
						const preview = await getV3GenerationBlueprint(gid);
						v3Studio.blueprint = preview;
						v3Studio.canvas = buildCanvasSkeleton(preview);
					} catch {
						// Stream will continue; preview can be recovered from status endpoints later.
					}
				})();
			},
			onGenerationWarning: (data) => {
				v3Studio.error = friendly(data.message ?? 'Generation warning');
				const gid = v3Studio.generationId;
				if (gid) {
					void refreshChunkedStatus(gid);
				}
			},
			onGenerationComplete: () => {
				const gid = v3Studio.generationId;
				if (gid) {
					void hydrateFromDocument(gid);
				}
			},
			onOpen: () => {
				const gid = v3Studio.generationId;
				if (gid && !v3Studio.activePack) {
					void hydrateFromDocument(gid);
				}
			},
			onError: (err) => {
				v3Studio.error = friendly(err);
				const gid = v3Studio.generationId;
				if (gid && !v3Studio.activePack) {
					void hydrateFromDocument(gid);
				}
			}
		});
	}

	async function handleChunkedApprove() {
		const chunked = v3Studio.chunkedState;
		if (!chunked) return;
		const generationId = chunked.generation_id;
		v3Studio.generationId = generationId;
		v3Studio.error = null;
		v3Studio.stage = 'fill';
		stage2Progress = { completed: [], failed: [], active: null };
		try {
			const next = await approveChunkedPlan(generationId);
			v3Studio.chunkedState = next;
			hydrateChunkedSectionState(next);
			syncStage2Progress(next);
			if (next.stage === 'assembly_blocked') {
				v3Studio.stage = 'skeleton';
				return;
			}
			connectChunkedStage2Stream(generationId);
		} catch (err) {
			v3Studio.error = friendly(err);
			v3Studio.stage = 'skeleton';
		}
	}

	async function handleChunkedRegenerate(note: string) {
		const chunked = v3Studio.chunkedState;
		if (!chunked) return;
		disconnectActiveChunkedStream();
		v3Studio.error = null;
		v3Studio.stage = 'fill';
		try {
			const next = await regenerateChunkedPlan({
				generation_id: chunked.generation_id,
				note
			});
			v3Studio.chunkedState = next;
			hydrateChunkedSectionState(next);
			syncStage2Progress(next);
			v3Studio.stage = 'skeleton';
		} catch (err) {
			v3Studio.error = friendly(err);
			v3Studio.stage = 'skeleton';
		}
	}

	async function handleChunkedRetrySection(sectionId: string) {
		const chunked = v3Studio.chunkedState;
		if (!chunked) return;
		disconnectActiveChunkedStream();
		v3Studio.error = null;
		v3Studio.stage = 'fill';
		try {
			const next = await retryChunkedSection({
				generation_id: chunked.generation_id,
				section_id: sectionId
			});
			v3Studio.chunkedState = next;
			hydrateChunkedSectionState(next);
			if (next.stage === 'assembly_blocked') {
				disconnectActiveChunkedStream();
				v3Studio.stage = 'skeleton';
			} else if (next.stage === 'blueprint_ready') {
				v3Studio.stage = 'fill';
				connectGenerationStream(next.generation_id);
			} else if (next.stage === 'stage2_running') {
				syncStage2Progress(next);
				v3Studio.stage = 'fill';
				connectChunkedStage2Stream(next.generation_id);
			} else {
				disconnectActiveChunkedStream();
				v3Studio.stage = 'skeleton';
			}
		} catch (err) {
			v3Studio.error = friendly(err);
			v3Studio.stage = 'skeleton';
		}
	}

	onDestroy(() => {
		disconnectActiveChunkedStream();
		v3Studio.streamCancel?.();
	});

	onMount(() => {
		void resumeChunkedFromQuery();
	});

	$effect(() => {
		setGenerationQuery(v3Studio.generationId);
	});

	async function handleDownloadPdf() {
		const gid = v3Studio.generationId;
		if (!gid) {
			pdfError = 'No generation id - try generating again.';
			return;
		}
		const policy = currentExportPolicy;
		if (!policy.enabled) {
			pdfError = 'Export is unavailable for the current booklet status.';
			return;
		}
		if (policy.requiresConfirm && !pdfConfirming) {
			pdfConfirming = true;
			const proceed = window.confirm(
				'This draft needs review before classroom use. Export this draft anyway?'
			);
			pdfConfirming = false;
			if (!proceed) return;
		}
		if (!schoolName.trim() || !teacherName.trim()) {
			pdfError = 'School name and teacher name are required.';
			return;
		}
		pdfLoading = true;
		pdfError = null;
		try {
			await downloadV3GenerationPdf(gid, {
				school_name: schoolName.trim(),
				teacher_name: teacherName.trim(),
				date: exportDate.trim() || null,
				include_toc: false,
				include_answers: includeAnswers
			});
			pdfOpen = false;
		} catch (err) {
			pdfError = friendly(err);
		} finally {
			pdfLoading = false;
		}
	}
</script>

<div class="min-h-screen bg-background pb-16">
	<div class="sticky top-0 z-10 border-b border-border/60 bg-background/95 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/75">
		<div class="mx-auto flex max-w-5xl items-center justify-between gap-3">
			<span class="text-sm font-semibold tracking-tight">Studio</span>
			<button
				type="button"
				class="text-xs text-muted-foreground underline-offset-4 hover:underline"
				onclick={handleStartOver}
			>
				Start over
			</button>
		</div>
	</div>

	{#if v3Studio.stage === 'intent'}
		<V3InputSurface onSubmit={handleInputSubmit} />
	{:else if v3Studio.stage === 'fill'}
		<div class="space-y-4">
			<V3PlanningState
				form={v3Studio.form}
				signals={v3Studio.signals}
				planningLabel={v3Studio.chunkedState?.stage === 'stage2_running'
					? 'Expanding section briefs and validating each section'
					: 'Turning your intent into a resource skeleton'}
				messages={v3Studio.chunkedState?.stage === 'stage2_running'
					? [
							'Expanding section briefs one by oneâ€¦',
							'Checking continuity across prior sectionsâ€¦',
							'Validating each section against plan constraintsâ€¦',
							'Attempting final assemblyâ€¦'
						]
					: undefined}
			/>
			{#if v3Studio.chunkedState?.structural_plan?.sections?.length}
				<div class="mx-auto flex max-w-3xl flex-wrap justify-center gap-2 px-4 stage2-progress">
					{#each v3Studio.chunkedState.structural_plan.sections as section (section.id)}
						<div
							class="section-pill rounded-full border px-3 py-1 text-xs font-medium transition-colors"
							class:done={stage2Progress.completed.includes(section.id)}
							class:active={stage2Progress.active === section.id}
							class:failed={stage2Progress.failed.includes(section.id)}
						>
							{section.id}
						</div>
					{/each}
				</div>
			{/if}
		</div>
		{:else if v3Studio.stage === 'skeleton' && v3Studio.chunkedState?.structural_plan}
			{#if v3Studio.signals}
				<div class="mx-auto max-w-4xl px-4 pt-6">
					<div class="rounded-2xl border border-border/60 bg-card p-4 shadow-sm">
						<div class="flex flex-wrap items-center gap-2">
							<span class="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-primary">
								{v3Studio.signals.inferred_lesson_mode.replace(/_/g, ' ')}
							</span>
							<span
								class={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${
									v3Studio.signals.lesson_mode_confidence === 'low'
										? 'bg-amber-100 text-amber-900'
										: 'bg-emerald-100 text-emerald-900'
								}`}
							>
								{v3Studio.signals.lesson_mode_confidence} confidence
							</span>
						</div>
						<p class="mt-3 text-sm text-muted-foreground">
							{v3Studio.signals.teacher_goal}
							{#if v3Studio.signals.lesson_mode_confidence === 'low'}
								If this inferred mode feels off, go back and sharpen the outcome or struggle before approving.
							{/if}
						</p>
					</div>
				</div>
			{/if}
			<V3PlanPreview plan={v3Studio.chunkedState.structural_plan} />
			<V3PlanActions
				failedSections={v3Studio.chunkedState.failed_sections}
				isRunning={v3Studio.chunkedState.stage === 'stage2_running'}
				onApprove={handleChunkedApprove}
				onRegenerate={handleChunkedRegenerate}
				onRetrySection={handleChunkedRetrySection}
			/>
		{:else if v3Studio.stage === 'edit'}
		{#if v3Studio.activePack}
			<div class="mx-auto max-w-4xl px-4 pt-4">
				<div class="flex justify-end">
					<button
						type="button"
						class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60"
						onclick={() => (pdfOpen = !pdfOpen)}
						disabled={!currentExportPolicy.enabled}
					>
						{currentExportPolicy.label}
					</button>
				</div>
				{#if pdfOpen}
					<div class="mt-3 rounded-lg border border-border/60 bg-card p-4 space-y-3">
						<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
							<label class="flex flex-col gap-1 text-sm">
								School name
								<input
									bind:value={schoolName}
									placeholder="Springfield High"
									class="rounded-md border border-input bg-background px-3 py-1.5 text-sm"
								/>
							</label>
							<label class="flex flex-col gap-1 text-sm">
								Teacher name
								<input
									bind:value={teacherName}
									placeholder="Ms. Johnson"
									class="rounded-md border border-input bg-background px-3 py-1.5 text-sm"
								/>
							</label>
							<label class="flex flex-col gap-1 text-sm">
								Date (optional)
								<input
									bind:value={exportDate}
									type="date"
									class="rounded-md border border-input bg-background px-3 py-1.5 text-sm"
								/>
							</label>
						</div>
						<label class="flex items-center gap-2 text-sm">
							<input bind:checked={includeAnswers} type="checkbox" />
							Include answers
						</label>
						{#if pdfError}
							<p class="text-sm text-destructive" role="alert">{pdfError}</p>
						{/if}
						<button
							type="button"
							class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60"
							onclick={handleDownloadPdf}
							disabled={pdfLoading || !schoolName.trim() || !teacherName.trim()}
						>
							{pdfLoading ? 'Generating PDF...' : 'Download PDF'}
						</button>
					</div>
				{/if}
			</div>
		{/if}
		{#if v3Studio.coherenceHint}
			<p class="mx-auto max-w-3xl px-4 pt-6 text-center text-sm text-muted-foreground">{v3Studio.coherenceHint}</p>
		{/if}
		{#if v3Studio.activePack}
			<V3BookletPackView
				pack={v3Studio.activePack}
				status={v3Studio.bookletStatus}
				issues={v3Studio.bookletIssues}
			/>
			<details class="mx-auto max-w-4xl px-4 pb-6">
				<summary class="cursor-pointer text-sm font-medium text-muted-foreground">Show generation progress</summary>
				<div class="pt-4">
					<V3Canvas sections={v3Studio.canvas} stage={v3Studio.stage} templateId={v3Studio.blueprint?.template_id ?? 'guided-concept-path'} />
				</div>
			</details>
		{:else}
			<V3Canvas sections={v3Studio.canvas} stage={v3Studio.stage} templateId={v3Studio.blueprint?.template_id ?? 'guided-concept-path'} />
		{/if}
	{/if}

	{#if v3Studio.error}
		<p class="mx-auto mt-6 max-w-xl px-4 text-center text-sm text-destructive" role="alert">{v3Studio.error}</p>
	{/if}
</div>
