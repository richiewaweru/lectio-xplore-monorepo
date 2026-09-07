<script lang="ts">
	import { Popover, PopoverTrigger, PopoverContent } from '$lib/components/ui/popover';
	import { renderInlineMarkdown } from '$lib/utils/markdown';

	let { term, definition }: { term: string; definition: string } = $props();
</script>

<Popover>
	<PopoverTrigger>
		<button
			class="inline cursor-pointer font-medium text-foreground underline decoration-dotted decoration-purple-500/70 underline-offset-2 transition-colors hover:text-foreground hover:decoration-purple-600"
			aria-label={`Definition of ${term}`}
			data-glossary-term="true"
		>
			{term}
		</button>
	</PopoverTrigger>
	<PopoverContent class="glass-panel w-56 rounded-[1.1rem] p-3 text-foreground">
		<div class="relative z-10">
			<div class="mb-1 text-xs font-semibold text-purple-700">{term}</div>
			<p class="text-xs leading-relaxed text-foreground/88">{@html renderInlineMarkdown(definition)}</p>
		</div>
	</PopoverContent>
</Popover>
