<script lang="ts">
	import { dragHandle, dragHandleZone, type DndEvent } from 'svelte-dnd-action';
	import { getComponentById, getComponentsByGroup } from 'lectio';
	import { GripVertical } from 'lucide-svelte';
	import type { DocumentStore } from '$lib/builder/stores/document.svelte';
	import type { DndRowItem } from '$lib/builder/stores/document.svelte';
	import { isPaletteDndItem } from '$lib/builder/stores/document.svelte';
	import PaletteItem from './PaletteItem.svelte';

	let {
		store,
		sheet = false
	}: {
		store: DocumentStore;
		/** Full-width, no side border (e.g. mobile bottom sheet). */
		sheet?: boolean;
	} = $props();

	const groups = [
		{ id: 1, label: 'Foundation' },
		{ id: 2, label: 'Definition & Knowledge' },
		{ id: 3, label: 'Examples & Process' },
		{ id: 4, label: 'Assessment & Practice' },
		{ id: 5, label: 'Alerts' },
		{ id: 6, label: 'Diagrams & Timeline' },
		{ id: 7, label: 'Simulation' }
	];

	function buildGroupItems(groupId: number): DndRowItem[] {
		return getComponentsByGroup(groupId).map((meta) => ({
			id: `palette:${groupId}:${meta.id}`,
			isPalette: true,
			component_id: meta.id
		}));
	}

	function initialPaletteState(): Record<number, DndRowItem[]> {
		const o: Record<number, DndRowItem[]> = {};
		for (const g of groups) {
			o[g.id] = buildGroupItems(g.id);
		}
		return o;
	}

	let paletteByGroup = $state<Record<number, DndRowItem[]>>(initialPaletteState());

	function handleConsider(groupId: number, e: CustomEvent<DndEvent<DndRowItem>>): void {
		paletteByGroup = { ...paletteByGroup, [groupId]: e.detail.items as DndRowItem[] };
	}

	function handleFinalize(groupId: number, _e: CustomEvent<DndEvent<DndRowItem>>): void {
		paletteByGroup = { ...paletteByGroup, [groupId]: buildGroupItems(groupId) };
	}

	function handleAdd(componentId: string): void {
		const sid = store.selectedSectionId ?? store.orderedSections[0]?.id;
		if (!sid) return;
		const newId = store.addBlock(sid, componentId);
		store.selectBlock(newId);
		store.startEditing(newId);
	}
</script>

<aside
	class="palette-sidebar shrink-0 overflow-y-auto bg-white {sheet
		? 'w-full border-0'
		: 'w-64 border-r border-slate-200'}"
	aria-label="Component palette"
>
	<p class="sticky top-0 z-10 border-b border-slate-100 bg-white px-3 py-2 text-sm font-semibold text-slate-800">
		Components
	</p>
	<div class="px-2 pb-4">
		{#each groups as group (group.id)}
			<div class="palette-group mt-3 first:mt-2">
				<h3 class="palette-group-label mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
					{group.label}
				</h3>
				<div
					use:dragHandleZone={{
						items: paletteByGroup[group.id] ?? [],
						type: 'canvas-block',
						flipDurationMs: 200,
						dropTargetStyle: { outline: '2px dashed #94a3b8' }
					}}
					onconsider={(e) => handleConsider(group.id, e)}
					onfinalize={(e) => handleFinalize(group.id, e)}
				>
					{#each paletteByGroup[group.id] ?? [] as item (item.id)}
						{#if isPaletteDndItem(item)}
							{@const meta = getComponentById(item.component_id)}
							{#if meta}
								<div
									class="mb-2 flex items-start gap-1 rounded-lg border border-transparent px-1 py-0.5 hover:border-slate-100"
								>
									<span
										class="drag-handle mt-2 inline-flex shrink-0 cursor-grab touch-none rounded p-0.5 text-slate-400 hover:bg-slate-100"
										aria-label="Drag to canvas"
										use:dragHandle
									>
										<GripVertical size={14} aria-hidden="true" />
									</span>
									<div class="min-w-0 flex-1">
										<PaletteItem {meta} onadd={handleAdd} />
									</div>
								</div>
							{/if}
						{/if}
					{/each}
				</div>
			</div>
		{/each}
	</div>
</aside>
