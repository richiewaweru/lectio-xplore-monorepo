<script lang="ts">
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { onDestroy, onMount } from 'svelte';

	import V3InputSurface from '$lib/components/studio/V3InputSurface.svelte';
	import V3PlanningState from '$lib/components/studio/V3PlanningState.svelte';
	import V3PlanPreview from '$lib/components/studio/V3PlanPreview.svelte';
	import V3PlanActions from '$lib/components/studio/V3PlanActions.svelte';
	import V3Canvas from '$lib/components/studio/V3Canvas.svelte';
	import V3BookletPackView from '$lib/components/studio/V3BookletPackView.svelte';
	import V3BookletIssuesPanel from '$lib/components/studio/V3BookletIssuesPanel.svelte';

	import {
		approveChunkedPlan,
		getLessonApproach,
		approveLessonApproach,
		rejectLessonApproach,
		connectV3ChunkedStream,
		connectV3StudioGenerationStream,
		downloadV3GenerationPdf,
		extractSignals,
		fetchV3Document,
		getChunkedPlan,
		getChunkedPlanStatus,
		getV3GenerationBlueprint,
		regenerateChunkedPlan,
		retryChunkedSection,
		startChunkedPlan
	} from '$lib/api/v3';
	import { isApiError } from '$lib/api/errors';
	import { createGenerationPoller } from '$lib/generation/generation-poller';
	import { resetV3Studio, v3Studio } from '$lib/stores/v3-studio.svelte';
	import { createBuilderLesson, listBuilderLessons } from '$lib/builder/api/lesson-crud';
	import { v3PackToBuilderDocument } from '$lib/builder/adapters/from-generation';
	import { v3StructuralPlanToBuilderDocument } from '$lib/builder/adapters/from-structural-plan';
	import { saveDocument } from '$lib/builder/persistence/idb-store';
	import {
		buildCanvasSkeleton,
		buildStructuralPlanCanvas,
		patchCanvasSection
	} from '$lib/studio/v3-canvas';
	import {
		getBookletExportPolicy,
		getBookletPrintReadiness
	} from '$lib/studio/v3-booklet';
	import { coerceV3DocumentToPack } from '$lib/studio/v3-document';
	import type { V3PackDocument } from '$lib/studio/v3-pack-to-lectio-document';
	import { mapPackSectionsToCanvas } from '$lib/studio/v3-print-canvas';
	import type {
		V3ChunkedPlan,
		V3ChunkedPlanState,
		V3ChunkedStatus,
		V3DraftPack,
		V3InputForm,
		V3VariantSpec
	} from '$lib/types/v3';

	let pdfLoading = $state(false);
	let recoveryBusy = $state(false);
	let lessonApproach = $state<Record<string, unknown> | null>(null);
	let teachingApproveBusy = $state(false);
	let pdfError = $state<string | null>(null);
	let pdfOpen = $state(false);
	let schoolName = $state('');
	let teacherName = $state('');
	let exportDate = $state('');
	let includeAnswers = $state(true);
	let builderLoading = $state(false);
	let builderError = $state<string | null>(null);
	let classLabel = $state<string | null>(null);
	let displayTitle = $state('');
	const currentExportPolicy = $derived(getBookletExportPolicy(v3Studio.bookletStatus));
	const currentPrintReadiness = $derived(
		getBookletPrintReadiness(v3Studio.bookletStatus, v3Studio.activePack)
	);
	const builderSourcePack = $derived(v3Studio.activePack ?? v3Studio.finalPack ?? v3Studio.draftPack);
	let stage2Progress = $state<{
		completed: string[];
		failed: string[];
		active: string | null;
	}>({ completed: [], failed: [], active: null });
	let documentPollInFlight = false;
	let documentPollGenerationId: string | null = null;
	let lastDocumentVersion: string | null = null;
	let hydratedDocumentGenerationId: string | null = null;
	let disconnectChunkedStream: (() => void) | null = null;
	const generationPoller = createGenerationPoller(async () => {
		if (documentPollGenerationId) await pollGenerationStatus(documentPollGenerationId);
	});

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
		builderLoading = false;
		builderError = null;
		pdfOpen = false;
		pdfError = null;
		displayTitle = '';
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

	type Stage2BriefPreview = {
		components: { component_id: string; content_intent: string }[];
		question_prompts: string[];
		visual_subject: string | null;
	};

	function paintCanvasFromPack(pack: V3DraftPack): void {
		v3Studio.canvas = mapPackSectionsToCanvas(
			pack.sections,
			pack.section_diagnostics,
			v3Studio.chunkedState?.structural_plan?.sections ?? []
		);
	}

	function clearRenderedBookletState(): void {
		v3Studio.canvas = [];
		v3Studio.draftPack = null;
		v3Studio.finalPack = null;
		v3Studio.activePack = null;
		v3Studio.bookletIssues = [];
		v3Studio.bookletStatus = 'streaming_preview';
		v3Studio.coherenceHint = null;
		pdfOpen = false;
		pdfError = null;
		builderError = null;
	}

	async function applyChunkedState(
		state: V3ChunkedPlanState,
		{
			resume: _resume = false,
			hydrateComplete = true,
			pollImmediately = true
		}: { resume?: boolean; hydrateComplete?: boolean; pollImmediately?: boolean } = {}
	): Promise<void> {
		const resolved = state;

		v3Studio.chunkedState = resolved;
		v3Studio.generationId = resolved.generation_id;
		hydrateChunkedSectionState(resolved);
		syncStage2Progress(resolved);
		if (shouldPollForChunkedState(resolved)) {
			startGenerationPolling(resolved.generation_id, { immediate: pollImmediately });
		}

		if (resolved.stage === 'awaiting_review' || resolved.stage === 'plan_ready') {
			disconnectActiveChunkedStream();
			clearRenderedBookletState();
			displayTitle = resolved.display_title ?? resolved.structural_plan?.lesson_intent.goal ?? '';
			if (resolved.structural_plan) {
				v3Studio.canvas = buildStructuralPlanCanvas(resolved.structural_plan);
			}
			v3Studio.stage = 'skeleton';
			return;
		}
		if (resolved.stage === 'awaiting_teaching_approval') {
			disconnectActiveChunkedStream();
			clearRenderedBookletState();
			displayTitle = resolved.display_title ?? displayTitle;
			try {
				lessonApproach = await getLessonApproach(resolved.generation_id);
			} catch (err) {
				v3Studio.error = friendly(err);
				lessonApproach = null;
			}
			v3Studio.stage = 'teaching_review';
			return;
		}
		if (
			resolved.stage === 'planning_forms' ||
			resolved.stage === 'queued' ||
			resolved.stage === 'writing_blocks' ||
			resolved.stage === 'assembling' ||
			resolved.stage === 'awaiting_visuals'
		) {
			// Native whole-lesson: teacher approved; form planner + writers run server-side and
			// persist a LectioDocumentV2. Keep a generating state and poll until the document lands.
			disconnectActiveChunkedStream();
			displayTitle = resolved.display_title ?? displayTitle;
			const hydrated = await hydrateFromDocument(resolved.generation_id);
			if (!hydrated && v3Studio.stage !== 'edit') {
				v3Studio.stage = 'generating';
			}
			return;
		}
		if (resolved.stage === 'ready') {
			disconnectActiveChunkedStream();
			displayTitle = resolved.display_title ?? displayTitle;
			await hydrateFromDocument(resolved.generation_id);
			return;
		}
		if (resolved.stage === 'assembly_blocked' || resolved.stage === 'stage2_error') {
			disconnectActiveChunkedStream();
			displayTitle = resolved.display_title ?? displayTitle;
			if (!v3Studio.activePack) {
				clearRenderedBookletState();
			}
			if (resolved.structural_plan && !v3Studio.activePack) {
				v3Studio.canvas = buildStructuralPlanCanvas(resolved.structural_plan);
			}
			v3Studio.stage = v3Studio.activePack ? 'edit' : 'skeleton';
			return;
		}
		if (resolved.stage === 'variants_running' && resolved.pack_id) {
			disconnectActiveChunkedStream();
			await goto(`/packs/${encodeURIComponent(resolved.pack_id)}`);
			return;
		}
		if (resolved.stage === 'stage2_running') {
			if (v3Studio.activePack && v3Studio.activePack.status !== 'streaming_preview') {
				disconnectActiveChunkedStream();
				v3Studio.stage = 'edit';
				return;
			}
			if (resolved.structural_plan && v3Studio.canvas.length === 0) {
				v3Studio.canvas = buildStructuralPlanCanvas(resolved.structural_plan);
			}
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
		if (resolved.stage === 'complete' || resolved.stage === 'completed') {
			disconnectActiveChunkedStream();
			v3Studio.stage = 'edit';
			try {
				const preview = await getV3GenerationBlueprint(resolved.generation_id);
				v3Studio.blueprint = preview;
			} catch {
				// Ignore missing preview and continue with persisted document hydration.
			}
			if (hydrateComplete) {
				await hydrateFromDocument(resolved.generation_id);
			}
		}
	}

	function stateFromPlanAndStatus(
		plan: V3ChunkedPlan,
		status: V3ChunkedStatus
	): V3ChunkedPlanState {
		const legacyStatus = status as V3ChunkedStatus & {
			structural_plan?: V3ChunkedPlan['structural_plan'];
			section_briefs?: Record<string, unknown>;
			display_title?: string | null;
		};
		return {
			generation_id: status.generation_id,
			pack_id: status.pack_id ?? plan.pack_id,
			stage: status.stage,
			structural_plan: legacyStatus.structural_plan ?? plan.structural_plan,
			section_briefs: legacyStatus.section_briefs ?? {},
			failed_sections: status.failed_sections,
			blueprint_id: status.blueprint_id,
			execution_started: status.execution_started,
			next_action: status.next_action,
			display_title: legacyStatus.display_title ?? plan.display_title,
			error: status.error,
			error_type: status.error_type,
			inferred_lesson_mode: plan.inferred_lesson_mode,
			lesson_mode_confidence: plan.lesson_mode_confidence,
			variants: plan.variants,
			variant_generation_ids: status.variant_generation_ids ?? plan.variant_generation_ids
		};
	}

	function mergeChunkedStatus(status: V3ChunkedStatus): V3ChunkedPlanState | null {
		const current = v3Studio.chunkedState;
		if (!current || current.generation_id !== status.generation_id) return null;
		return {
			...current,
			pack_id: status.pack_id ?? current.pack_id,
			stage: status.stage,
			failed_sections: status.failed_sections,
			blueprint_id: status.blueprint_id,
			execution_started: status.execution_started,
			next_action: status.next_action,
			error: status.error,
			error_type: status.error_type
		};
	}

	async function resumeChunkedFromQuery(): Promise<void> {
		if (!browser) return;
		const generationId = new URL(window.location.href).searchParams.get('generation_id');
		if (!generationId) return;
		v3Studio.error = null;
		try {
			const [plan, status] = await Promise.all([
				getChunkedPlan(generationId),
				getChunkedPlanStatus(generationId)
			]);
			const state = stateFromPlanAndStatus(plan, status);
			v3Studio.chunkedState = state;
			v3Studio.generationId = generationId;
			const hydrated = await hydrateFromDocument(generationId);
			if (hydrated) {
				hydratedDocumentGenerationId = generationId;
				lastDocumentVersion = status.doc_version;
			}
			await applyChunkedState(state, {
				resume: true,
				hydrateComplete: false,
				pollImmediately: false
			});
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

	function progressStageFromDocument(document: Record<string, unknown>): string | null {
		const progress = document.progress;
		if (typeof progress !== 'object' || progress === null) return null;
		const stage = (progress as { stage?: unknown }).stage;
		return typeof stage === 'string' ? stage : null;
	}

	function isTerminalProgressStage(stage: string | null): boolean {
		return stage === 'completed' || stage === 'failed';
	}

	function shouldPollForChunkedState(state: V3ChunkedPlanState): boolean {
		if (
			state.stage === 'awaiting_review' ||
			state.stage === 'plan_ready' ||
			state.stage === 'awaiting_teaching_approval' ||
			state.stage === 'assembly_blocked' ||
			state.stage === 'stage2_error' ||
			state.stage === 'complete'
		) {
			return false;
		}
		if (state.stage === 'completed') return false;
		if (state.next_action === 'done') return false;
		if (state.execution_started) return true;
		// Native whole-lesson: forms/writers run server-side after teacher approval; the
		// chunked stage stays in execution phases until the document is persisted, so keep polling.
		if (
			state.stage === 'queued' ||
			state.stage === 'planning_forms' ||
			state.stage === 'writing_blocks' ||
			state.stage === 'assembling' ||
			state.stage === 'awaiting_visuals'
		) {
			return true;
		}
		if (state.stage === 'ready') return false;
		if (['stage2_running', 'stage2_complete', 'blueprint_ready'].includes(state.stage)) return true;
		return state.next_action === 'wait_for_stage2' || state.next_action === 'generation_running';
	}

	function stopGenerationPolling(): void {
		generationPoller.stop();
		documentPollGenerationId = null;
		lastDocumentVersion = null;
		hydratedDocumentGenerationId = null;
	}

	async function pollGenerationStatus(generationId: string): Promise<void> {
		if (!browser || documentPollInFlight) return;
		documentPollInFlight = true;
		try {
			const status = await getChunkedPlanStatus(generationId);
			const merged = mergeChunkedStatus(status);
			if (merged) {
				await applyChunkedState(merged, { hydrateComplete: false });
			}
			const versionChanged =
				typeof status.doc_version === 'string' && status.doc_version !== lastDocumentVersion;
			if (hydratedDocumentGenerationId !== generationId || versionChanged) {
				const hydrated = await hydrateFromDocument(generationId);
				if (hydrated) {
					hydratedDocumentGenerationId = generationId;
					lastDocumentVersion = status.doc_version;
				}
			}
			if (status.stage === 'complete' || status.next_action === 'done') {
				stopGenerationPolling();
			}
		} catch {
			// Keep the current UI state if status polling fails.
		} finally {
			documentPollInFlight = false;
		}
	}

	function startGenerationPolling(
		generationId: string,
		{ immediate = true }: { immediate?: boolean } = {}
	): void {
		if (documentPollGenerationId === generationId && generationPoller.isRunning()) return;
		stopGenerationPolling();
		documentPollGenerationId = generationId;
		generationPoller.start({ immediate });
	}

	async function hydrateFromDocument(generationId: string): Promise<boolean> {
		try {
			const document = await fetchV3Document(generationId);
			const progressStage = progressStageFromDocument(document);
			const pack = coerceV3DocumentToPack(generationId, document, {
				templateId: v3Studio.blueprint?.template_id ?? 'guided-concept-path'
			});
			if (!pack) {
				if (progressStage === 'failed' || progressStage === 'completed') {
					stopGenerationPolling();
					v3Studio.streamCancel?.();
					v3Studio.streamCancel = null;
					v3Studio.stage = 'skeleton';
					v3Studio.error =
						progressStage === 'completed'
							? 'Generation completed, but its resource snapshot was not saved.'
							: 'Generation failed before a resource snapshot was saved.';
				}
				return false;
			}
			v3Studio.draftPack = pack;
			v3Studio.activePack = pack;
			if (pack.status === 'final_ready' || pack.status === 'final_with_warnings') {
				v3Studio.finalPack = pack;
			}
			v3Studio.bookletStatus = pack.status;
			v3Studio.bookletIssues = pack.booklet_issues;
			paintCanvasFromPack(pack);
			if (progressStage === 'failed') {
				v3Studio.coherenceHint = null;
				v3Studio.error = 'Generation failed before the resource was finalised.';
				stopGenerationPolling();
				v3Studio.streamCancel?.();
				v3Studio.streamCancel = null;
				if (pack.sections.length > 0) {
					v3Studio.stage = 'edit';
				}
			} else if (progressStage === 'completed') {
				v3Studio.coherenceHint = null;
				stopGenerationPolling();
				v3Studio.streamCancel?.();
				v3Studio.streamCancel = null;
				v3Studio.stage = 'edit';
			} else if (progressStage && !isTerminalProgressStage(progressStage)) {
				v3Studio.stage = 'fill';
			} else if (pack.status !== 'streaming_preview') {
				v3Studio.coherenceHint = null;
				v3Studio.stage = 'edit';
			}
			return true;
		} catch {
			return false;
		}
	}

	async function handleVisualRegenerated(): Promise<void> {
		if (v3Studio.generationId) {
			await hydrateFromDocument(v3Studio.generationId);
		}
	}

	async function refreshChunkedStatus(generationId: string): Promise<void> {
		try {
			const status = await getChunkedPlanStatus(generationId);
			const state = mergeChunkedStatus(status);
			if (state) await applyChunkedState(state, { hydrateComplete: false });
		} catch {
			// Keep current UI state if status refresh fails.
		}
	}

	async function handleInputSubmit(
		form: V3InputForm,
		submittedClassLabel: string | null,
		variants: V3VariantSpec[]
	) {
		v3Studio.error = null;
		builderError = null;
		classLabel = submittedClassLabel;
		v3Studio.form = form;
		v3Studio.stage = 'fill';
		try {
			v3Studio.signals = await extractSignals(form);
			const chunkedState = await startChunkedPlan({
				signals: v3Studio.signals,
				form,
				variants
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
				v3Studio.canvas = patchCanvasSection(v3Studio.canvas, sectionId, (section) => ({
					...section,
					sectionStatus: 'running'
				}));
			},
			onSectionDone(sectionId, brief?: Stage2BriefPreview) {
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
				v3Studio.canvas = patchCanvasSection(v3Studio.canvas, sectionId, (section) => ({
					...section,
					sectionStatus: 'complete',
					stage2Preview: brief
						? {
								componentIntents: brief.components.map((component) => ({
									componentId: component.component_id,
									intent: component.content_intent
								})),
								questionPrompts: brief.question_prompts,
								visualSubject: brief.visual_subject
							}
						: section.stage2Preview
				}));
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
				v3Studio.canvas = patchCanvasSection(v3Studio.canvas, sectionId, (section) => ({
					...section,
					sectionStatus: 'running'
				}));
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
				v3Studio.canvas = patchCanvasSection(v3Studio.canvas, sectionId, (section) => ({
					...section,
					sectionStatus: 'failed'
				}));
			},
			onStage2Complete(failedSections) {
				if (v3Studio.chunkedState) {
					v3Studio.chunkedState = {
						...v3Studio.chunkedState,
						stage: 'stage2_complete',
						failed_sections: failedSections
					};
				}
				stage2Progress = {
					completed: stage2Progress.completed,
					failed: failedSections,
					active: null
				};
				disconnectActiveChunkedStream();
				connectGenerationStream(generationId);
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
				if (v3Studio.chunkedState?.structural_plan) {
					v3Studio.canvas = buildStructuralPlanCanvas(v3Studio.chunkedState.structural_plan);
				}
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
		v3Studio.streamCancel = null;
		v3Studio.error = null;
		v3Studio.stage = 'fill';
		startGenerationPolling(generationId);
		v3Studio.streamCancel = connectV3StudioGenerationStream(generationId, {
			onPoke: () => {
				void pollGenerationStatus(generationId);
			},
			onOpen: () => {
				void pollGenerationStatus(generationId);
			},
			onError: () => {
				void pollGenerationStatus(generationId);
			}
		});
	}


	async function handleChunkedApprove() {
		const chunked = v3Studio.chunkedState;
		if (!chunked) return;
		const generationId = chunked.generation_id;
		v3Studio.generationId = generationId;
		v3Studio.error = null;
		builderError = null;
		try {
			const structuralPlan = chunked.structural_plan;
			if (!structuralPlan) {
				throw new Error('The lesson plan is missing its structural plan.');
			}
			if (structuralPlan.document_contract_version === 2) {
				const next = await approveChunkedPlan(generationId, { display_title: displayTitle.trim() });
				await continueChunkedStage2(next);
				return;
			}
			const existing = (await listBuilderLessons()).find(
				(lesson) => lesson.source_generation_id === generationId
			);
			if (existing) {
				await goto(`/builder/${existing.id}?generation_id=${generationId}`);
				return;
			}
			const lesson = v3StructuralPlanToBuilderDocument(structuralPlan, {
				generationId,
				title: displayTitle
			});
			const created = await createBuilderLesson({
				source_type: 'v3_generation',
				source_generation_id: generationId,
				title: lesson.title,
				class_label: classLabel,
				document: lesson
			});
			await saveDocument(created.document);
			await goto(`/builder/${created.id}?generation_id=${generationId}`);
		} catch (err) {
			v3Studio.error = friendly(err);
			v3Studio.stage = 'skeleton';
		}
	}

	async function continueChunkedStage2(next: V3ChunkedPlanState): Promise<void> {
		if (next.stage === 'assembly_blocked' || next.stage === 'stage2_error') {
			await applyChunkedState(next);
			return;
		}
		if (next.stage === 'variants_running' && next.pack_id) {
			v3Studio.chunkedState = next;
			v3Studio.generationId = next.generation_id;
			await goto(`/packs/${encodeURIComponent(next.pack_id)}`);
			return;
		}
		v3Studio.chunkedState = next;
		v3Studio.generationId = next.generation_id;
		hydrateChunkedSectionState(next);
		syncStage2Progress(next);
		startGenerationPolling(next.generation_id);
		connectChunkedStage2Stream(next.generation_id);
	}

	async function handleChunkedResume() {
		const chunked = v3Studio.chunkedState;
		if (!chunked) return;
		recoveryBusy = true;
		v3Studio.error = null;
		try {
			const next = await approveChunkedPlan(chunked.generation_id, { display_title: displayTitle.trim() });
			await continueChunkedStage2(next);
		} catch (err) {
			v3Studio.error = friendly(err);
		} finally {
			recoveryBusy = false;
		}
	}

	async function handleTeachingApproachApprove() {
		const chunked = v3Studio.chunkedState;
		if (!chunked || !lessonApproach) return;
		teachingApproveBusy = true;
		v3Studio.error = null;
		try {
			const review = (lessonApproach.teaching_review || {}) as { revision?: number };
			await approveLessonApproach(chunked.generation_id, {
				expected_revision: Number(review.revision || 1),
				teacher_note: 'Approved'
			});
			startGenerationPolling(chunked.generation_id, { immediate: true });
			v3Studio.stage = 'generating';
		} catch (err) {
			v3Studio.error = friendly(err);
		} finally {
			teachingApproveBusy = false;
		}
	}

	async function handleTeachingApproachReject() {
		const chunked = v3Studio.chunkedState;
		if (!chunked || !lessonApproach) return;
		teachingApproveBusy = true;
		v3Studio.error = null;
		try {
			const review = (lessonApproach.teaching_review || {}) as { revision?: number };
			await rejectLessonApproach(chunked.generation_id, {
				expected_revision: Number(review.revision || 1),
				teacher_note: 'Rejected'
			});
			v3Studio.stage = 'skeleton';
		} catch (err) {
			v3Studio.error = friendly(err);
		} finally {
			teachingApproveBusy = false;
		}
	}

	async function handleChunkedRegenerate(note: string) {
		const chunked = v3Studio.chunkedState;
		if (!chunked) return;
		disconnectActiveChunkedStream();
		v3Studio.error = null;
		clearRenderedBookletState();
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
		builderError = null;
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

	async function handleRetryFailedSections() {
		const chunked = v3Studio.chunkedState;
		if (!chunked || chunked.failed_sections.length === 0) return;
		recoveryBusy = true;
		v3Studio.error = null;
		try {
			for (const sectionId of chunked.failed_sections) {
				await retryChunkedSection({ generation_id: chunked.generation_id, section_id: sectionId });
			}
			await refreshChunkedStatus(chunked.generation_id);
		} catch (err) {
			v3Studio.error = friendly(err);
		} finally {
			recoveryBusy = false;
		}
	}

	onDestroy(() => {
		disconnectActiveChunkedStream();
		stopGenerationPolling();
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

	async function handleOpenInBuilder() {
		const generationId = v3Studio.generationId;
		const pack = builderSourcePack;
		if (!generationId || !pack) {
			builderError = 'A renderable lesson is required before opening Builder.';
			return;
		}
		builderLoading = true;
		builderError = null;
		try {
			const packSnapshot = $state.snapshot(pack) as V3PackDocument;
			const lesson = v3PackToBuilderDocument(packSnapshot, {
				routeGenerationId: generationId
			});
			const created = await createBuilderLesson({
				source_type: 'v3_generation',
				source_generation_id: generationId,
				title: lesson.title,
				class_label: classLabel,
				document: lesson
			});
			await saveDocument(created.document);
			await goto(`/builder/${created.id}`);
		} catch (err) {
			builderError = friendly(err);
		} finally {
			builderLoading = false;
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
			{#if stage2Progress.completed.length === 0 && stage2Progress.active === null}
				<p class="mx-auto max-w-3xl px-4 text-center text-sm font-medium text-muted-foreground">
					Designing your lesson…
				</p>
			{/if}
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
			{#if v3Studio.canvas.length > 0}
				<V3Canvas
					sections={v3Studio.canvas}
					stage={v3Studio.stage}
					templateId={v3Studio.blueprint?.template_id ?? 'guided-concept-path'}
					onRetrySection={handleChunkedRetrySection}
				/>
			{/if}
			{#if v3Studio.bookletIssues.length}
				<div class="mx-auto max-w-4xl px-4">
					<V3BookletIssuesPanel issues={v3Studio.bookletIssues} title="Review flags" generationId={v3Studio.generationId} pack={v3Studio.activePack} onRegenerated={handleVisualRegenerated} />
				</div>
			{/if}
		</div>
		{:else if v3Studio.stage === 'teaching_review' && lessonApproach}
			<section class="mx-auto max-w-3xl space-y-6 px-4 py-8">
				<header class="space-y-2">
					<p class="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Lesson approach</p>
					<h2 class="text-2xl font-semibold text-foreground">Review the teaching plan</h2>
					<p class="text-sm text-muted-foreground">
						Approve the pedagogical arc before forms and writers run. Read the last brief first.
					</p>
				</header>
				{#if lessonApproach.teaching_plan}
					{@const plan = lessonApproach.teaching_plan as {
						arc?: string;
						anchor_usage?: Record<string, string>;
						misconception_focus_ids?: string[];
						sections?: Array<{
							slot_id: string;
							specific_purpose?: string;
							blocks?: Array<{
								id: string;
								intent: string;
								brief: string;
								evidence?: string;
								departure_reason?: string | null;
								source_question_ids?: string[];
							}>;
						}>;
					}}
					<div class="rounded-xl border border-border/70 bg-card p-4">
						<h3 class="text-sm font-semibold">Arc</h3>
						<p class="mt-2 text-sm leading-relaxed text-foreground">{plan.arc}</p>
					</div>
					{#if plan.anchor_usage}
						<div class="rounded-xl border border-border/70 bg-card p-4">
							<h3 class="text-sm font-semibold">Anchor usage</h3>
							<ul class="mt-2 space-y-1 text-sm text-muted-foreground">
								{#each Object.entries(plan.anchor_usage) as [slot, usage]}
									<li><span class="font-medium text-foreground">{slot}:</span> {usage}</li>
								{/each}
							</ul>
						</div>
					{/if}
					{#if plan.misconception_focus_ids?.length}
						<p class="text-sm text-muted-foreground">
							Focused misconceptions: {plan.misconception_focus_ids.join(', ')}
						</p>
					{/if}
					{#each [...(plan.sections || [])].reverse() as section}
						<article class="rounded-xl border border-border/70 bg-card p-4">
							<h3 class="text-sm font-semibold uppercase tracking-wide">{section.slot_id}</h3>
							{#if section.specific_purpose}
								<p class="mt-1 text-sm text-muted-foreground">{section.specific_purpose}</p>
							{/if}
							{#each [...(section.blocks || [])].reverse() as block}
								<div class="mt-3 border-t border-border/50 pt-3">
									<p class="text-xs font-semibold text-muted-foreground">{block.id} · {block.intent}</p>
									<p class="mt-1 text-sm text-foreground">{block.brief}</p>
									{#if block.departure_reason}
										<p class="mt-1 text-xs text-amber-800">Departure: {block.departure_reason}</p>
									{/if}
								</div>
							{/each}
						</article>
					{/each}
				{/if}
				{#if Array.isArray(lessonApproach.teaching_qc) && lessonApproach.teaching_qc.length}
					<div class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
						<p class="font-semibold">Advisory warnings</p>
						<ul class="mt-2 list-disc space-y-1 pl-5">
							{#each lessonApproach.teaching_qc as finding}
								<li>{(finding as { code?: string; message?: string }).code}: {(finding as { message?: string }).message}</li>
							{/each}
						</ul>
					</div>
				{/if}
				<div class="flex flex-wrap gap-3">
					<button
						class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
						disabled={teachingApproveBusy}
						onclick={handleTeachingApproachApprove}
					>
						{teachingApproveBusy ? 'Approving…' : 'Approve teaching plan'}
					</button>
					<button
						class="rounded-md border border-border px-4 py-2 text-sm font-semibold text-foreground disabled:opacity-50"
						disabled={teachingApproveBusy}
						onclick={handleTeachingApproachReject}
					>
						Reject
					</button>
				</div>
			</section>
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
			<div class="mx-auto max-w-3xl px-4 pb-2">
				<label class="block text-sm font-medium text-foreground" for="v3-display-title">
					Lesson title
				</label>
				<input
					id="v3-display-title"
					class="mt-2 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
					bind:value={displayTitle}
					maxlength="120"
				/>
			</div>
			<V3PlanActions
				isRunning={recoveryBusy || v3Studio.chunkedState.stage === 'stage2_running'}
				recoveryAction={v3Studio.chunkedState.stage === 'assembly_blocked' && v3Studio.chunkedState.failed_sections.length > 0
					? 'retry_failed_sections'
					: v3Studio.chunkedState.stage === 'stage2_error' ||
							(v3Studio.chunkedState.stage === 'assembly_blocked' && v3Studio.chunkedState.failed_sections.length === 0)
						? 'resume_stage2'
						: null}
				onApprove={handleChunkedApprove}
				onRegenerate={handleChunkedRegenerate}
				onRecovery={v3Studio.chunkedState.stage === 'assembly_blocked' && v3Studio.chunkedState.failed_sections.length > 0
					? handleRetryFailedSections
					: handleChunkedResume}
			/>
	{:else if v3Studio.stage === 'generating'}
			<section class="mx-auto max-w-3xl space-y-4 px-4 py-16 text-center">
				<div class="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-primary/30 border-t-primary" aria-hidden="true"></div>
				<h2 class="text-xl font-semibold text-foreground">Building your lesson…</h2>
				<p class="text-sm text-muted-foreground">
					Teaching plan approved. Planning forms, writing each block, and assembling the printable
					document. This can take several minutes — you can leave this page and return to
					<code>/studio?generation_id={v3Studio.generationId}</code> or the lesson viewer.
				</p>
			</section>
		{:else if v3Studio.stage === 'edit'}
		{#if v3Studio.activePack}
			{#if v3Studio.chunkedState?.stage === 'assembly_blocked' || v3Studio.chunkedState?.stage === 'stage2_error'}
				<div class="mx-auto max-w-4xl px-4 pt-4">
					<button
						type="button"
						class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60"
						disabled={recoveryBusy}
						onclick={v3Studio.chunkedState.stage === 'assembly_blocked' && v3Studio.chunkedState.failed_sections.length > 0
							? handleRetryFailedSections
							: handleChunkedResume}
					>
						{v3Studio.chunkedState.stage === 'assembly_blocked' && v3Studio.chunkedState.failed_sections.length > 0
							? 'Retry failed sections'
							: 'Resume generation'}
					</button>
				</div>
			{/if}
			<div class="mx-auto max-w-4xl px-4 pt-4">
				<div class="rounded-lg border border-border/60 bg-card px-4 py-3">
					<p class="text-sm font-medium">{currentPrintReadiness.label}</p>
					<p class="mt-1 text-sm text-muted-foreground">{currentPrintReadiness.detail}</p>
				</div>
				<div class="mt-3 flex flex-wrap justify-end gap-2">
					<button
						type="button"
						class="rounded-md border border-input px-4 py-2 text-sm font-medium disabled:opacity-60"
						onclick={handleOpenInBuilder}
						disabled={!builderSourcePack || !v3Studio.generationId || builderLoading}
					>
						{builderLoading ? 'Opening Builder...' : 'Open in Builder'}
					</button>
					<button
						type="button"
						class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60"
						onclick={() => (pdfOpen = !pdfOpen)}
						disabled={!currentExportPolicy.enabled}
					>
						{currentExportPolicy.label}
					</button>
				</div>
				{#if builderError}
					<p class="mt-3 text-sm text-destructive" role="alert">{builderError}</p>
				{/if}
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
		{#if v3Studio.bookletIssues.length}
			<div class="mx-auto max-w-4xl px-4 pt-4">
				<V3BookletIssuesPanel issues={v3Studio.bookletIssues} title="Review flags" generationId={v3Studio.generationId} pack={v3Studio.activePack} onRegenerated={handleVisualRegenerated} />
			</div>
		{/if}
		{#if v3Studio.activePack}
			<V3BookletPackView
				pack={v3Studio.activePack}
				status={v3Studio.bookletStatus}
				issues={v3Studio.bookletIssues}
				showIssues={false}
			/>
			<details class="mx-auto max-w-4xl px-4 pb-6">
				<summary class="cursor-pointer text-sm font-medium text-muted-foreground">Show generation progress</summary>
				<div class="pt-4">
					<V3Canvas sections={v3Studio.canvas} stage={v3Studio.stage} templateId={v3Studio.blueprint?.template_id ?? 'guided-concept-path'} onRetrySection={handleChunkedRetrySection} />
				</div>
			</details>
		{:else}
			<V3Canvas sections={v3Studio.canvas} stage={v3Studio.stage} templateId={v3Studio.blueprint?.template_id ?? 'guided-concept-path'} onRetrySection={handleChunkedRetrySection} />
		{/if}
	{/if}

	{#if v3Studio.error}
		<p class="mx-auto mt-6 max-w-xl px-4 text-center text-sm text-destructive" role="alert">{v3Studio.error}</p>
	{/if}
</div>
