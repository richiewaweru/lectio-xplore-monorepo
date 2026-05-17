<script lang="ts">
	import { fromStore } from 'svelte/store';

	import { authUser } from '$lib/stores/auth';
	import type { ArchitectMode } from '$lib/types/v3';

	type Props = {
		value: ArchitectMode;
		onChange: (mode: ArchitectMode) => void;
	};

	let { value, onChange }: Props = $props();
	const user = fromStore(authUser);
	const isAdmin = $derived(user.current?.email?.endsWith('@lectio.app') ?? false);

	function setMode(mode: ArchitectMode) {
		if (value === mode) return;
		onChange(mode);
	}
</script>

{#if isAdmin}
	<div class="flex items-center gap-2" aria-label="Architect mode">
		<span class="text-xs font-medium text-muted-foreground">Architect mode</span>
		<div class="inline-flex rounded-md border border-border bg-muted/40 p-0.5">
			<button
				type="button"
				class={`rounded px-2 py-1 text-xs transition ${
					value === 'standard'
						? 'bg-background text-foreground shadow-sm'
						: 'text-muted-foreground hover:text-foreground'
				}`}
				aria-pressed={value === 'standard'}
				onclick={() => setMode('standard')}
			>
				Standard
			</button>
			<button
				type="button"
				class={`rounded px-2 py-1 text-xs transition ${
					value === 'chunked'
						? 'bg-background text-foreground shadow-sm'
						: 'text-muted-foreground hover:text-foreground'
				}`}
				aria-pressed={value === 'chunked'}
				onclick={() => setMode('chunked')}
			>
				Chunked
			</button>
		</div>
	</div>
{/if}
