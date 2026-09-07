<script lang="ts">
	import type { CanvasComponent } from '$lib/types/v3';
	import V3PatchIndicator from '$lib/components/studio/V3PatchIndicator.svelte';

	interface Props {
		component: CanvasComponent;
	}

	let { component }: Props = $props();
</script>

<div
	class="v3-canvas-component rounded-lg border border-border/40 p-3"
	class:opacity-60={component.status === 'pending'}
	data-status={component.status}
>
	<div class="mb-2 flex items-center justify-between gap-2">
		<span class="text-sm font-semibold text-foreground">{component.teacher_label}</span>
		{#if component.status === 'patched'}
			<V3PatchIndicator />
		{/if}
	</div>

	{#if component.status === 'pending'}
		<div class="v3-skeleton h-16 animate-pulse rounded-md bg-muted"></div>
	{:else if component.status === 'ready' || component.status === 'patched'}
		<p class="text-xs text-muted-foreground">Content merged into section preview below.</p>
	{:else if component.status === 'failed'}
		<p class="text-sm text-destructive">Could not generate this block.</p>
	{/if}

	{#if component.data}
		<details class="mt-2 rounded border border-border/40 bg-background/60 p-2">
			<summary class="cursor-pointer text-xs font-medium text-muted-foreground">Inspect data</summary>
			<pre class="mt-2 overflow-auto whitespace-pre-wrap text-[11px]">{JSON.stringify(component.data, null, 2)}</pre>
		</details>
	{/if}
</div>
