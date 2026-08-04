<script lang="ts">
	import {
		BookOpen,
		Image,
		LayoutList,
		ListChecks,
		MessageCircle,
		NotebookPen,
		PencilRuler,
		Sparkles,
		TriangleAlert,
		X
	} from 'lucide-svelte';
	import type { DocumentStore } from '$lib/builder/stores/document.svelte';
	import { filterPaletteGroups } from './palette-overlay';

	let {
		store,
		onclose,
		onadd
	}: {
		store: DocumentStore;
		onclose: () => void;
		onadd?: (componentId: string) => void | Promise<void>;
	} = $props();

	let query = $state('');
	const filteredGroups = $derived(filterPaletteGroups(query));

	const intentClasses: Record<number, string> = {
		1: 'bg-slate-100 text-slate-700',
		2: 'bg-emerald-50 text-emerald-700',
		3: 'bg-blue-50 text-blue-700',
		4: 'bg-indigo-50 text-indigo-700',
		5: 'bg-rose-50 text-rose-700',
		6: 'bg-fuchsia-50 text-fuchsia-700',
		7: 'bg-orange-50 text-orange-700'
	};

	function iconFor(name: string) {
		switch (name) {
			case 'book-open':
				return BookOpen;
			case 'notebook-pen':
				return NotebookPen;
			case 'list-checks':
				return ListChecks;
			case 'pencil-ruler':
				return PencilRuler;
			case 'message-circle':
				return MessageCircle;
			case 'triangle-alert':
				return TriangleAlert;
			case 'image':
				return Image;
			case 'layout-list':
				return LayoutList;
			case 'sparkles':
				return Sparkles;
			default:
				return BookOpen;
		}
	}

	function addBlock(componentId: string): void {
		if (onadd) {
			void onadd(componentId);
			return;
		}
		const sectionId = store.selectedSectionId ?? store.orderedSections[0]?.id;
		if (!sectionId) return;
		const newId = store.addBlock(sectionId, componentId);
		store.selectBlock(newId);
		store.startEditing(newId);
		onclose();
	}
</script>

<div
	class="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4"
	role="button"
	tabindex="-1"
	onclick={onclose}
	onkeydown={(e) => e.key === 'Escape' && onclose()}
>
	<div
		role="dialog"
		aria-label="Add block"
		tabindex="-1"
		class="w-full max-w-none overflow-hidden rounded-t-2xl border border-slate-200 bg-white shadow-2xl sm:w-[min(92vw,400px)] sm:rounded-xl"
		onclick={(e) => e.stopPropagation()}
		onkeydown={(e) => e.stopPropagation()}
	>
		<div class="flex items-center justify-between border-b border-slate-100 px-4 py-3">
			<div>
				<p class="text-sm font-semibold text-slate-900">Add block</p>
				<p class="text-xs text-slate-500">Choose a component by teaching intent.</p>
			</div>
			<button
				type="button"
				class="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
				aria-label="Close palette"
				onclick={onclose}
			>
				<X size={16} />
			</button>
		</div>

		<div class="border-b border-slate-100 px-4 py-3">
			<input
				type="text"
				class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
				placeholder="Search components"
				bind:value={query}
				data-testid="palette-search"
			/>
		</div>

		<div class="max-h-[70vh] overflow-y-auto p-3 sm:max-h-[65vh]">
			{#if filteredGroups.length === 0}
				<p class="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
					No components match "{query}".
				</p>
			{:else}
				{#each filteredGroups as entry (entry.group.id)}
					{@const Icon = iconFor(entry.group.icon)}
					<div class="mb-3 last:mb-0">
						<div class="mb-2 flex items-center gap-2 px-1">
							<span
								class="inline-flex h-6 w-6 items-center justify-center rounded-md {intentClasses[entry.group.id] ??
									'bg-slate-100 text-slate-700'}"
							>
								<Icon size={14} />
							</span>
							<div>
								<p class="text-xs font-semibold uppercase tracking-wide text-slate-600">{entry.group.label}</p>
								<p class="text-[11px] text-slate-500">{entry.group.description}</p>
							</div>
						</div>

						<div class="space-y-1">
							{#each entry.components as meta (meta.id)}
								<button
									type="button"
									class="w-full rounded-lg border border-slate-200 px-3 py-2 text-left hover:border-blue-300 hover:bg-blue-50/40"
									data-testid="palette-overlay-item"
									onclick={() => addBlock(meta.id)}
								>
									<p class="text-sm font-medium text-slate-900">{meta.teacherLabel}</p>
									<p class="text-xs text-slate-500">{meta.teacherDescription}</p>
								</button>
							{/each}
						</div>
					</div>
				{/each}
			{/if}
		</div>
	</div>
</div>
