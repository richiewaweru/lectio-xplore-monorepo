<script lang="ts">
	import { browser } from '$app/environment';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { onDestroy, onMount } from 'svelte';
	import { isApiError } from '$lib/api/errors';
	import AppShell from '$lib/builder/components/shell/AppShell.svelte';
	import ConceptCardReview from '$lib/builder/components/ConceptCardReview.svelte';
	import { createDocumentStore } from '$lib/builder/stores/document.svelte';
	import { loadBuilderLessonWithFallback } from '$lib/builder/persistence/server-sync';
	import { logout } from '$lib/stores/auth';
	import { fetchV3Document, getChunkedPlan, getChunkedPlanStatus } from '$lib/api/v3';
	import type { V3VisualBlock } from '$lib/api/v3';
	import {
		partitionGenerationIssues,
		v3PackToBuilderDocument
	} from '$lib/builder/adapters/from-generation';
	import type { BuilderIssue } from '$lib/builder/issues';
	import type { V3PackDocument } from '$lib/studio/v3-pack-to-lectio-document';
	import { getBookletStatusSummary, isBookletStatus } from '$lib/studio/v3-booklet';
	import {
		isTerminalGenerationDocument,
		pendingPlanFromStructuralPlan,
		type PendingPlanSection
	} from '$lib/builder/streaming/generation-stream';
	import {
		isDeleteOrBackspace,
		isModifierD,
		isModifierS,
		isModifierShiftZ,
		isModifierZ,
		isTextEditingTarget
	} from '$lib/builder/utils/shortcuts';

	const store = createDocumentStore();
	let ready = $state(false);
	let loadWarning = $state<string | null>(null);
	let loadError = $state<{ status: number; title: string; detail: string } | null>(null);
	let pendingPlan = $state<PendingPlanSection[]>([]);
	let sectionProgress = $state<Record<string, string>>({});
	let generationTerminal = $state(false);
	let documentLevelIssues = $state<BuilderIssue[]>([]);
	let dismissedDocumentIssueIds = $state<string[]>([]);
	let generationBlocker = $state<{ title: string; detail: string; failedSections: string[] } | null>(null);
	let generationStatusLine = $state<string | null>(null);
	let visualBlocks = $state<V3VisualBlock[]>([]);
	let pollInterval: ReturnType<typeof setInterval> | null = null;
	let pollInFlight = false;
	let hasHydratedGeneration = false;
	let lastDocVersion: string | null = null;
	let awaitingCardReview = $state(false);

	const id = $derived(page.params.id);
	const generationId = $derived(page.url.searchParams.get('generation_id'));
	const dismissedIssuesKey = $derived(id ? `lectio:dismissed-doc-issues:${id}` : '');

	function dismissDocumentIssue(issueId: string): void {
		if (dismissedDocumentIssueIds.includes(issueId)) return;
		dismissedDocumentIssueIds = [...dismissedDocumentIssueIds, issueId];
		documentLevelIssues = documentLevelIssues.filter((issue) => issue.id !== issueId);
		if (browser && dismissedIssuesKey) {
			localStorage.setItem(dismissedIssuesKey, JSON.stringify(dismissedDocumentIssueIds));
		}
	}

	function stopPolling(): void {
		if (pollInterval !== null) clearInterval(pollInterval);
		pollInterval = null;
	}

	function setGenerationWarning(error: unknown): void {
		const next =
			error instanceof Error ? `Generation update delayed: ${error.message}` : 'Generation update delayed.';
		if (loadWarning !== next) loadWarning = next;
	}

	function visualUrlSwaps(nextVisuals: V3VisualBlock[]) {
		const previousById = new Map(visualBlocks.map((visual) => [visual.visual_id, visual]));
		return nextVisuals.flatMap((visual) => {
			const previous = previousById.get(visual.visual_id);
			return previous?.image_url && visual.image_url && previous.image_url !== visual.image_url
				? [{
					sectionId: visual.attaches_to,
					oldUrl: previous.image_url,
					newUrl: visual.image_url,
					frameIndex: visual.frame_index
				}]
				: [];
		});
	}

	async function pollGeneration(): Promise<void> {
		if (!generationId || pollInFlight || !store.document) return;
		pollInFlight = true;
		try {
			if (pendingPlan.length === 0) {
				try {
					const plan = await getChunkedPlan(generationId);
					pendingPlan = pendingPlanFromStructuralPlan(plan.structural_plan);
				} catch {
					// The document snapshot can still land even if planning state is temporarily unavailable.
				}
			}
			const status = await getChunkedPlanStatus(generationId);
			if (status.stage === 'assembly_blocked' || status.stage === 'stage2_error') {
				generationBlocker = {
					title: status.stage === 'assembly_blocked' ? 'Generation needs recovery' : 'Generation stopped',
					detail: status.error ?? 'Open Studio to retry or resume this generation.',
					failedSections: status.failed_sections
				};
				generationTerminal = true;
				stopPolling();
				return;
			}
			if (
				(status.stage === 'awaiting_review' || status.stage === 'plan_ready') &&
				!status.execution_started
			) {
				awaitingCardReview = true;
				generationBlocker = null;
				generationTerminal = false;
				stopPolling();
				return;
			}
			awaitingCardReview = false;
			const versionChanged =
				typeof status.doc_version === 'string' && status.doc_version !== lastDocVersion;
			const chunkedTerminal = status.stage === 'complete' || status.next_action === 'done';
			if (!hasHydratedGeneration || versionChanged || chunkedTerminal) {
				let rawPack: Record<string, unknown>;
				try {
					rawPack = await fetchV3Document(generationId);
				} catch (error) {
					if (isApiError(error) && error.status === 404 && !chunkedTerminal) return;
					setGenerationWarning(error);
					return;
				}
				const pack = rawPack as V3PackDocument;
				const adapted = v3PackToBuilderDocument(pack, { routeGenerationId: generationId });
				store.insertSectionsFromGeneration(adapted, pendingPlan);
				const nextVisualBlocks = (pack.visual_blocks ?? []) as V3VisualBlock[];
				const visualSwaps = visualUrlSwaps(nextVisualBlocks);
				let preservedEditedVisual = false;
				if (visualSwaps.length > 0 && !store.refreshGeneratedVisualUrls(visualSwaps)) {
					loadWarning = 'A regenerated image is ready, but Builder preserved your locally edited image.';
					preservedEditedVisual = true;
				}
				visualBlocks = nextVisualBlocks;
				store.refreshGenerationIssues(adapted);
				const partitioned = partitionGenerationIssues(
					pack,
					adapted.sections.map((section) => section.id)
				);
				documentLevelIssues = partitioned.documentLevelIssues.filter(
					(issue) => !dismissedDocumentIssueIds.includes(issue.id)
				);
				sectionProgress = { ...(pack.progress?.sections ?? {}) };
				generationTerminal = isTerminalGenerationDocument(pack) || chunkedTerminal;
				generationStatusLine = isBookletStatus(pack.status)
					? getBookletStatusSummary(pack.status)
					: null;
				if (!preservedEditedVisual) loadWarning = null;
				hasHydratedGeneration = true;
				if (typeof status.doc_version === 'string') lastDocVersion = status.doc_version;
				if (generationTerminal) stopPolling();
			}
		} catch (error) {
			setGenerationWarning(error);
		} finally {
			pollInFlight = false;
		}
	}

	function startPolling(): void {
		if (!generationId) return;
		stopPolling();
		void pollGeneration();
		pollInterval = setInterval(() => void pollGeneration(), 4000);
	}

	function handleCardsApproved(): void {
		awaitingCardReview = false;
		generationTerminal = false;
		startPolling();
	}

	onDestroy(stopPolling);

	onMount(() => {
		if (!id) {
			loadError = {
				status: 404,
				title: 'Lesson not found',
				detail: 'This lesson id is missing or invalid.'
			};
			return;
		}
		if (browser && dismissedIssuesKey) {
			try {
				const stored = JSON.parse(localStorage.getItem(dismissedIssuesKey) ?? '[]');
				dismissedDocumentIssueIds = Array.isArray(stored)
					? stored.filter((value): value is string => typeof value === 'string')
					: [];
			} catch {
				dismissedDocumentIssueIds = [];
			}
		}
		void loadBuilderLessonWithFallback(id)
			.then(({ document: doc, source }) => {
				if (!doc) {
					loadError = {
						status: 404,
						title: 'Lesson not found',
						detail: 'This lesson was not found or is no longer available.'
					};
					return;
				}
				store.loadDocument(doc);
				loadWarning =
					source === 'idb'
						? 'Loaded local cached copy. Server sync will resume when connectivity is restored.'
						: null;
				ready = true;
				startPolling();
			})
			.catch(async (error) => {
				if (isApiError(error) && error.status === 401) {
					logout();
					await goto('/login', { replaceState: true });
					return;
				}
				if (isApiError(error) && error.status === 404) {
					loadError = {
						status: 404,
						title: 'Lesson not found',
						detail: 'This lesson does not exist or you no longer have access to it.'
					};
					return;
				}
				loadError = {
					status: 500,
					title: 'Unable to load lesson',
					detail: error instanceof Error ? error.message : 'Please retry in a moment.'
				};
			});
	});

	$effect(() => {
		if (!browser || !ready || !store.document) return;

		function onKey(e: KeyboardEvent): void {
			if (isTextEditingTarget(e.target)) return;

			if (isModifierZ(e)) {
				e.preventDefault();
				store.undo();
				return;
			}
			if (isModifierShiftZ(e)) {
				e.preventDefault();
				store.redo();
				return;
			}
			if (isModifierS(e)) {
				e.preventDefault();
				void store.flushSave();
				return;
			}
			if (e.key === 'Escape') {
				if (store.editingBlockId) {
					store.stopEditing();
				} else {
					store.deselectBlock();
				}
				return;
			}
			if (e.key === 'Enter' && store.selectedBlockId && !store.editingBlockId) {
				e.preventDefault();
				store.startEditing(store.selectedBlockId);
				return;
			}
			if (isModifierD(e) && store.selectedBlockId) {
				e.preventDefault();
				const sid = store.getSectionIdForBlock(store.selectedBlockId);
				if (sid) {
					const nid = store.duplicateBlock(sid, store.selectedBlockId);
					store.selectBlock(nid);
				}
				return;
			}
			if (isDeleteOrBackspace(e) && store.selectedBlockId && !store.editingBlockId) {
				if (confirm('Remove this block? You can undo.')) {
					const sid = store.getSectionIdForBlock(store.selectedBlockId);
					if (sid) {
						store.removeBlock(sid, store.selectedBlockId);
					}
				}
				e.preventDefault();
			}
		}

		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	});
</script>

{#if loadError}
	<section class="mx-auto max-w-3xl p-6">
		<div class="rounded-xl border border-red-200 bg-red-50 p-5 text-red-800">
			<p class="text-xs font-semibold uppercase tracking-wide text-red-700">{loadError.status}</p>
			<h1 class="mt-1 text-xl font-bold">{loadError.title}</h1>
			<p class="mt-2 text-sm">{loadError.detail}</p>
			<div class="mt-4">
				<a
					href="/lessons"
					class="inline-flex rounded-lg border border-red-200 bg-white px-3 py-1.5 text-sm font-semibold text-red-700 hover:bg-red-100/40"
				>
					Back to lessons
				</a>
			</div>
		</div>
	</section>
{:else if !ready || !store.document}
	<section class="mx-auto max-w-4xl p-6" aria-busy="true" aria-live="polite">
		<div class="mb-4 h-6 w-56 animate-pulse rounded bg-slate-200"></div>
		<div class="space-y-3 rounded-2xl border border-slate-200 bg-white p-5">
			<div class="h-5 w-40 animate-pulse rounded bg-slate-200"></div>
			<div class="h-4 w-full animate-pulse rounded bg-slate-100"></div>
			<div class="h-4 w-11/12 animate-pulse rounded bg-slate-100"></div>
			<div class="h-4 w-9/12 animate-pulse rounded bg-slate-100"></div>
		</div>
		<p class="mt-4 text-sm text-slate-500">Loading lesson workspace...</p>
	</section>
{:else if awaitingCardReview && generationId}
	<ConceptCardReview
		packId={generationId}
		title={store.document.title}
		onApproved={handleCardsApproved}
	/>
{:else}
	{#if generationId}
		<a
			class="builder-print-hidden mb-3 inline-flex rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-800"
			href={`/packs/${encodeURIComponent(generationId)}/items`}
		>
			Review shared quiz · edit in pack
		</a>
	{/if}
	{#if generationBlocker && generationId}
		<section class="builder-print-hidden mb-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900" role="alert">
			<p class="font-semibold">{generationBlocker.title}</p>
			<p class="mt-1">{generationBlocker.detail}</p>
			{#if generationBlocker.failedSections.length > 0}
				<p class="mt-1">Failed sections: {generationBlocker.failedSections.join(', ')}</p>
			{/if}
			<a class="mt-2 inline-flex rounded border border-red-300 bg-white px-3 py-1.5 font-medium" href={`/studio?generation_id=${encodeURIComponent(generationId)}`}>Open recovery in Studio</a>
		</section>
	{/if}
	{#if loadWarning}
		<p class="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
			{loadWarning}
		</p>
	{/if}
	{#if generationTerminal && generationStatusLine}
		<p class="builder-print-hidden mb-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700" role="status">{generationStatusLine}</p>
	{/if}
	<AppShell
		document={store.document}
		{store}
		{pendingPlan}
		{sectionProgress}
		{generationTerminal}
		{documentLevelIssues}
		onDismissDocumentIssue={dismissDocumentIssue}
		{generationId}
		{visualBlocks}
		onVisualRegenerated={pollGeneration}
	/>
{/if}
