<script lang="ts">
	import { templateRegistry } from 'lectio';
	import type { DocumentStore } from '$lib/builder/stores/document.svelte';

	let {
		store,
		insertIndex
	}: {
		store: DocumentStore;
		/** Index in ordered section list where the new section is inserted. */
		insertIndex: number;
	} = $props();

	let open = $state(false);
	let title = $state('New section');
	let templateId = $state(templateRegistry[0]?.contract.id ?? 'open-canvas');

	function submit(): void {
		store.addSection(templateId, insertIndex, title);
		open = false;
		title = 'New section';
	}
</script>

<div class="add-section-control flex justify-center py-1">
	{#if !open}
		<button
			type="button"
			class="rounded-full border border-dashed border-slate-300 bg-white px-3 py-1 text-xs font-medium text-slate-600 hover:border-blue-400 hover:text-blue-700"
			data-testid="add-section-toggle"
			onclick={() => (open = true)}
		>
			+ Section
		</button>
	{:else}
		<div
			class="w-full max-w-lg rounded-lg border border-slate-200 bg-white p-3 text-sm shadow-sm"
		>
			<label class="mb-1 block text-slate-600" for="new-sec-title-{insertIndex}">Section title</label>
			<input
				id="new-sec-title-{insertIndex}"
				class="mb-2 w-full rounded border border-slate-300 px-2 py-1"
				bind:value={title}
			/>
			<label class="mb-1 block text-slate-600" for="new-sec-tmpl-{insertIndex}">Template</label>
			<select
				id="new-sec-tmpl-{insertIndex}"
				class="mb-3 w-full rounded border border-slate-300 px-2 py-1"
				bind:value={templateId}
			>
				{#each templateRegistry as def (def.contract.id)}
					<option value={def.contract.id}>{def.contract.name}</option>
				{/each}
			</select>
			<div class="flex gap-2">
				<button
					type="button"
					class="rounded-md bg-blue-600 px-3 py-1 text-white hover:bg-blue-700"
					onclick={submit}
				>
					Add
				</button>
				<button
					type="button"
					class="rounded-md border border-slate-300 px-3 py-1 hover:bg-slate-50"
					onclick={() => (open = false)}
				>
					Cancel
				</button>
			</div>
		</div>
	{/if}
</div>
