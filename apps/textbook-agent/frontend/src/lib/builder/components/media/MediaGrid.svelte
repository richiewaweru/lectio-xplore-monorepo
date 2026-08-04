<script lang="ts">
	import type { MediaReference } from 'lectio';

	let {
		mediaList,
		selectedId = '',
		filterType,
		onpick
	}: {
		mediaList: MediaReference[];
		selectedId?: string;
		filterType?: 'video' | 'image' | 'audio';
		onpick: (id: string) => void;
	} = $props();

	const filtered = $derived(
		filterType ? mediaList.filter((m) => m.type === filterType) : mediaList
	);
</script>

{#if filtered.length === 0}
	<p class="text-sm text-slate-500">No matching items in this lesson yet.</p>
{:else}
	<ul class="grid grid-cols-2 gap-2 sm:grid-cols-3" role="list">
		{#each filtered as m (m.id)}
			<li>
				<button
					type="button"
					class="w-full rounded-lg border p-2 text-left transition-colors hover:bg-slate-50 {selectedId === m.id
						? 'border-blue-500 ring-1 ring-blue-500'
						: 'border-slate-200'}"
					onclick={() => onpick(m.id)}
				>
					<div class="mb-1 flex aspect-video items-center justify-center overflow-hidden rounded bg-slate-100 text-xs text-slate-500">
						{#if m.type === 'image'}
							<img src={m.url} alt="" class="max-h-full max-w-full object-contain" />
						{:else if m.type === 'video'}
							<span class="px-2 text-center font-medium">Video</span>
						{:else}
							<span>Audio</span>
						{/if}
					</div>
					<p class="truncate text-xs text-slate-700">{m.filename ?? m.url.slice(0, 40)}</p>
				</button>
			</li>
		{/each}
	</ul>
{/if}
