<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		preset = null,
		className,
		children
	}: {
		preset?: { id?: string } | null;
		className?: string;
		children: Snippet;
	} = $props();
</script>

<div data-testid="template-runtime-surface" data-preset={preset?.id ?? ''} class={className}>
	{@render children()}
</div>
