<script lang="ts">
	import type { InterviewContent } from '$lib/schema/types';
	import { Card } from '$lib/components/ui/card';
	import { MessageCircle } from 'lucide-svelte';
	import { renderBlockMarkdown } from '$lib/utils/markdown';

	let { content }: { content: InterviewContent } = $props();
</script>

<Card class="border-l-4 border-l-orange-400 bg-orange-50/50 rh-pad-card" data-print-container="atomic">
	<div class="flex rh-gap-cluster">
		<MessageCircle class="mt-0.5 h-5 w-5 shrink-0 text-orange-500" />
		<div class="rh-gap-component-tight">
			<div class="space-y-2">
				<p class="eyebrow text-orange-600">Explain it</p>
				<div class="lectio-rich text-sm leading-7 text-foreground">{@html renderBlockMarkdown(content.prompt)}</div>
				<p class="text-xs italic text-muted-foreground">Audience: {content.audience}</p>
			</div>

			{#if content.follow_up}
				<div class="border-t border-orange-200 pt-3">
					<p class="text-xs font-medium text-orange-600">Follow-up</p>
					<div class="lectio-rich mt-1 text-sm leading-relaxed text-foreground/80">
						{@html renderBlockMarkdown(content.follow_up)}
					</div>
				</div>
			{/if}
		</div>
	</div>
</Card>
