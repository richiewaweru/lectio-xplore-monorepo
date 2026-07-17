<script lang="ts">
	import { browser } from '$app/environment';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { onDestroy, onMount } from 'svelte';
	import { isApiError } from '$lib/api/errors';
	import AppShell from '$lib/builder/components/shell/AppShell.svelte';
	import { createDocumentStore } from '$lib/builder/stores/document.svelte';
	import { loadBuilderLessonWithFallback } from '$lib/builder/persistence/server-sync';
	import { logout } from '$lib/stores/auth';
	import { fetchV3Document, getChunkedPlan } from '$lib/api/v3';
	import { v3PackToBuilderDocument } from '$lib/builder/adapters/from-generation';
	import type { V3PackDocument } from '$lib/studio/v3-pack-to-lectio-document';
	import {
		allPlannedSectionsPresent,
		isTerminalPackStatus,
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
	let pollInterval: ReturnType<typeof setInterval> | null = null;
	let pollInFlight = false;

	const id = $derived(page.params.id);
	const generationId = $derived(page.url.searchParams.get('generation_id'));

	function stopPolling(): void {
		if (pollInterval !== null) clearInterval(pollInterval);
		pollInterval = null;
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
			const rawPack = await fetchV3Document(generationId);
			const pack = rawPack as V3PackDocument;
			const adapted = v3PackToBuilderDocument(pack, { routeGenerationId: generationId });
			store.insertSectionsFromGeneration(adapted, pendingPlan);
			if (
				isTerminalPackStatus(pack.status) ||
				(store.document && allPlannedSectionsPresent(store.document, pendingPlan))
			) stopPolling();
		} catch (error) {
			loadWarning = error instanceof Error ? `Generation update delayed: ${error.message}` : 'Generation update delayed.';
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
					href="/builder"
					class="inline-flex rounded-lg border border-red-200 bg-white px-3 py-1.5 text-sm font-semibold text-red-700 hover:bg-red-100/40"
				>
					Back to Builder lessons
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
{:else}
	{#if loadWarning}
		<p class="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
			{loadWarning}
		</p>
	{/if}
	<AppShell document={store.document} {store} {pendingPlan} />
{/if}
