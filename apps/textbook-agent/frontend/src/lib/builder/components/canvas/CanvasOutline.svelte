<script lang="ts">
	import { dragHandleZone, type DndEvent } from 'svelte-dnd-action';
	import type { DocumentSection } from 'lectio';
	import type { DocumentStore } from '$lib/builder/stores/document.svelte';

	let { store }: { store: DocumentStore } = $props();

	let outlineItems = $state<DocumentSection[]>([]);

	$effect(() => {
		outlineItems = store.orderedSections.map((s) => ({ ...s }));
	});

	function handleConsider(e: CustomEvent<DndEvent<DocumentSection>>): void {
		outlineItems = e.detail.items as DocumentSection[];
	}

	function handleFinalize(e: CustomEvent<DndEvent<DocumentSection>>): void {
		outlineItems = e.detail.items as DocumentSection[];
		const ids = outlineItems.map((i) => i.id);
		store.reorderSections(ids);
	}
</script>

<nav
	class="canvas-outline sticky top-0 hidden h-screen w-11 shrink-0 border-l border-slate-200 bg-white/90 py-4 md:block"
	aria-label="Section outline"
>
	<div
		use:dragHandleZone={{
			items: outlineItems,
			type: 'outline-section',
			flipDurationMs: 200,
			dropTargetStyle: { outline: '2px dashed #94a3b8' },
			dropFromOthersDisabled: true
		}}
		onconsider={handleConsider}
		onfinalize={handleFinalize}
		class="flex h-full flex-col items-center gap-2"
	>
		{#each outlineItems as section (section.id)}
			<a
				href="#section-{section.id}"
				data-testid="outline-section-link"
				title={`Section ${section.position + 1}: ${section.title}`}
				class="inline-flex h-6 w-6 items-center justify-center rounded-full transition-colors hover:bg-slate-100"
				onclick={() => store.selectSection(section.id)}
			>
				<span
					class="h-2.5 w-2.5 rounded-full {store.selectedSectionId === section.id
						? 'bg-blue-600 ring-2 ring-blue-200'
						: 'bg-slate-400'}"
				></span>
			</a>
		{/each}
	</div>
</nav>
