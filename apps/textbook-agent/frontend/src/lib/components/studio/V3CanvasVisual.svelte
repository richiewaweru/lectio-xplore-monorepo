<script lang="ts">
	import type { CanvasVisual } from '$lib/types/v3';

	interface Props {
		visual: CanvasVisual;
	}

	let { visual }: Props = $props();
</script>

<div class="v3-canvas-visual rounded-lg border border-dashed border-border/60 p-3">
	<h4 class="mb-2 text-sm font-semibold">Visual</h4>
	{#if visual.status === 'pending'}
		<div class="v3-skeleton h-40 animate-pulse rounded-md bg-muted"></div>
	{:else if visual.image_url}
		<img src={visual.image_url} alt="" class="max-h-64 w-full rounded-md object-contain" />
	{/if}
</div>
