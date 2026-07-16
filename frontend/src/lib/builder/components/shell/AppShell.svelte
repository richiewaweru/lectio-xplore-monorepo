<script lang="ts">
	import { browser } from '$app/environment';
	import { onMount, tick } from 'svelte';
	import { basePresetMap, LectioThemeSurface } from 'lectio';
	import type { LessonDocument } from 'lectio';
	import BlockCanvas from '$lib/builder/components/canvas/BlockCanvas.svelte';
	import CanvasOutline from '$lib/builder/components/canvas/CanvasOutline.svelte';
	import PaletteOverlay from '$lib/builder/components/palette/PaletteOverlay.svelte';
	import DocumentToolbar from '$lib/builder/components/toolbar/DocumentToolbar.svelte';
	import MediaManager from '$lib/builder/components/media/MediaManager.svelte';
	import VersionPanel from '$lib/builder/components/versions/VersionPanel.svelte';
	import OfflineSyncHooks from '$lib/builder/components/shell/OfflineSyncHooks.svelte';
	import { Plus } from 'lucide-svelte';
	import { saveVersionSnapshot } from '$lib/builder/persistence/idb-store';
	import type { DocumentStore } from '$lib/builder/stores/document.svelte';
	import type { PendingPlanSection } from '$lib/builder/streaming/generation-stream';

	let { document, store, pendingPlan = [] }: { document: LessonDocument; store: DocumentStore; pendingPlan?: PendingPlanSection[] } = $props();

	const preset = $derived(basePresetMap[document.preset_id] ?? null);

	let paletteOpen = $state(false);
	let mediaManagerOpen = $state(false);
	let versionPanelOpen = $state(false);
	let printPreviewActive = $state(false);

	/** Mutable refs for 30-minute auto-version (avoid stale interval closure). */
	const va = { docId: '', lastM: 0, lastA: 0 };

	$effect(() => {
		const d = store.document;
		if (!d) return;
		if (va.docId !== d.id) {
			va.docId = d.id;
			va.lastA = Date.now();
			va.lastM = Date.now();
			return;
		}
		void d.updated_at;
		va.lastM = Date.now();
	});

	onMount(() => {
		if (!browser || typeof indexedDB === 'undefined') return;
		const THIRTY_MS = 30 * 60 * 1000;
		const id = setInterval(() => {
			const d = store.document;
			if (!d) return;
			const now = Date.now();
			if (now - va.lastA < THIRTY_MS) return;
			if (va.lastM <= va.lastA) return;
			void saveVersionSnapshot(d.id, d, 'Auto-saved version').then(() => {
				va.lastA = Date.now();
			});
		}, 60_000);
		return () => clearInterval(id);
	});

	async function handlePaletteAdd(componentId: string): Promise<void> {
		paletteOpen = false;

		await tick();

		const sectionId = store.selectedSectionId ?? store.orderedSections[0]?.id;
		if (!sectionId) return;

		const newId = store.addBlock(sectionId, componentId);
		store.selectBlock(newId);

		await tick();

		const el = globalThis.document.querySelector(`[data-block-id="${newId}"]`);
		el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
	}

	function scrollToNextIssue(): void {
		globalThis.document.querySelector('[data-unresolved-issue]')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
	}
</script>

<div
	class="builder-shell flex min-h-screen flex-col bg-slate-100"
	class:builder-print-preview={printPreviewActive}
>
	<OfflineSyncHooks />
	<DocumentToolbar
		document={store.document ?? document}
		saveStatus={store.saveStatus}
		onOpenMedia={() => (mediaManagerOpen = true)}
		onOpenHistory={() => (versionPanelOpen = true)}
		lessonId={store.document?.id ?? document.id}
		printPreviewActive={printPreviewActive}
		onTogglePrintPreview={() => (printPreviewActive = !printPreviewActive)}
		onRetrySave={() => void store.flushSave()}
		onNextIssue={scrollToNextIssue}
	/>
	<div class="flex flex-1 overflow-hidden">
		<main
			class="builder-main min-w-0 flex-1 overflow-y-auto bg-gradient-to-b from-slate-100 via-slate-100 to-slate-200/70 p-4 sm:p-6"
			data-testid="builder-main"
		>
			<div class="builder-print-hidden sticky top-0 z-10 mx-auto mb-3 flex w-full max-w-4xl items-center justify-between rounded-b-lg bg-slate-100/95 pb-3 pt-2 backdrop-blur-sm">
				<div>
					<p class="text-xs font-semibold uppercase tracking-wide text-slate-600">Builder workspace</p>
					<p class="text-xs text-slate-500">
						{store.selectedSectionId
							? `Section selected: ${store.orderedSections.find((s) => s.id === store.selectedSectionId)?.title ?? 'Untitled'}`
							: 'Select a section to add blocks'}
					</p>
				</div>
				<button
					type="button"
					class="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700"
					aria-label="Add block"
					onclick={() => (paletteOpen = true)}
				>
					<Plus size={16} />
					Add block
				</button>
			</div>

			{#if preset}
				<LectioThemeSurface {preset}>
					{#snippet children()}
						<BlockCanvas {store} {pendingPlan} />
					{/snippet}
				</LectioThemeSurface>
			{:else}
				<p class="text-sm text-amber-800">Unknown preset "{document.preset_id}" - showing unstyled canvas.</p>
				<BlockCanvas {store} {pendingPlan} />
			{/if}
		</main>
		<CanvasOutline {store} />
	</div>
</div>

{#if mediaManagerOpen}
	<MediaManager {store} onclose={() => (mediaManagerOpen = false)} />
{/if}

{#if store.document}
	<VersionPanel bind:open={versionPanelOpen} document={store.document} {store} />
{/if}

{#if paletteOpen}
	<PaletteOverlay {store} onclose={() => (paletteOpen = false)} onadd={handlePaletteAdd} />
{/if}
