<script lang="ts">
	import type { DocumentSection } from 'lectio';
	import type { DocumentStore } from '$lib/builder/stores/document.svelte';
	import { issuesForSection } from '$lib/builder/issues';

	let {
		section,
		store,
		isFirstSection = false
	}: { section: DocumentSection; store: DocumentStore; isFirstSection?: boolean } = $props();

	let editingTitle = $state(false);
	let titleDraft = $state('');
	const unresolvedCount = $derived(issuesForSection(section).filter((issue) => !issue.resolved).length);

	$effect(() => {
		titleDraft = section.title;
	});

	function commitTitle(): void {
		editingTitle = false;
		if (titleDraft.trim() !== section.title) {
			store.updateSectionTitle(section.id, titleDraft.trim() || 'Untitled');
		}
	}

	function deleteSection(): void {
		const n = section.block_ids.length;
		if (
			confirm(
				`Delete this section and its ${n} block${n === 1 ? '' : 's'}? You can undo.`
			)
		) {
			store.removeSection(section.id);
		}
	}
</script>

<div
	id="section-{section.id}"
	class="section-divider scroll-mt-4 flex flex-wrap items-center justify-between gap-2 border-t-2 border-slate-300 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700 {isFirstSection
		? 'section-divider-first'
		: ''}"
>
	{#if editingTitle}
		<input
			class="min-w-[8rem] flex-1 rounded border border-slate-300 px-2 py-1 font-semibold"
			bind:value={titleDraft}
			onblur={commitTitle}
			onkeydown={(e) => {
				if (e.key === 'Enter') {
					e.preventDefault();
					(e.target as HTMLInputElement).blur();
				}
				if (e.key === 'Escape') {
					titleDraft = section.title;
					editingTitle = false;
				}
			}}
		/>
	{:else}
		<button
			type="button"
			class="text-left hover:underline"
			onclick={() => {
				store.selectSection(section.id);
				editingTitle = true;
			}}
		>
			Section {section.position + 1}: {section.title}
			{#if unresolvedCount}<span class="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">⚠ {unresolvedCount}</span>{/if}
		</button>
	{/if}
	<button
		type="button"
		class="section-divider-actions rounded-md p-1 text-red-600 hover:bg-red-50"
		title="Delete section"
		aria-label="Delete section"
		onclick={deleteSection}
	>
		<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M3 6h18M8 6V4h8v2M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M10 11v6M14 11v6"/></svg>
	</button>
</div>
