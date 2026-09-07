<script lang="ts">
	import type { MediaReference } from '$lib/teacher/document';
	import { componentRenderMap } from '$lib/lectio/registry/render-map';

	let {
		componentId,
		content,
		media = {}
	}: {
		componentId: string;
		content: Record<string, unknown>;
		media?: Record<string, MediaReference>;
	} = $props();

	const Component = $derived(componentRenderMap[componentId] ?? null);
</script>

{#if Component}
	<Component {content} {media} />
{:else}
	<div class="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
		Unknown component: {componentId}
	</div>
{/if}

