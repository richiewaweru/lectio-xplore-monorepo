<script lang="ts">
	import { fromStore } from 'svelte/store';

	import { authUser } from '$lib/stores/auth';
	import type { ArchitectMode } from '$lib/types/v3';

	type Props = {
		selected: ArchitectMode;
		onModeChange: (mode: ArchitectMode) => void;
	};

	let { selected, onModeChange }: Props = $props();
	const user = fromStore(authUser);
	const isAdmin = $derived(true);

	function setMode(mode: ArchitectMode) {
		if (selected === mode) return;
		onModeChange(mode);
	}
</script>

{#if isAdmin}
	<div class="flex items-center gap-2" role="group" aria-label="Architect mode">
		<span class="text-xs font-medium text-muted-foreground">Architect mode</span>
		<div class="inline-flex rounded-md border border-border bg-muted/40 p-0.5">
			<button
				type="button"
				class={`rounded px-2 py-1 text-xs transition ${
					selected === 'standard'
						? 'bg-background text-foreground shadow-sm'
						: 'text-muted-foreground hover:text-foreground'
				}`}
				aria-pressed={selected === 'standard'}
				onclick={() => setMode('standard')}
			>
				Standard
			</button>
			<button
				type="button"
				class={`rounded px-2 py-1 text-xs transition ${
					selected === 'chunked'
						? 'bg-background text-foreground shadow-sm'
						: 'text-muted-foreground hover:text-foreground'
				}`}
				aria-pressed={selected === 'chunked'}
				onclick={() => setMode('chunked')}
			>
				Chunked
			</button>
		</div>
	</div>
{/if}
