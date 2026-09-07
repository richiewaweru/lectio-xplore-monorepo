<script lang="ts">
	import type { Snippet } from 'svelte';

	import type { TemplatePresetDefinition } from '$lib/templates/types';
	import { cn } from '$lib/utils';

	let {
		preset = null,
		className,
		children
	}: {
		preset?: TemplatePresetDefinition | null;
		className?: string;
		children: Snippet;
	} = $props();
</script>

<div class={cn('lectio-runtime', className)} data-lectio-preset={preset?.id}>
	{@render children()}
</div>
