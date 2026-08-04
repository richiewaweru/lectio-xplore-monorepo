<script lang="ts">
	import type { ProseContent, RichParagraph } from '$lib/contract/document';
	import { asRichText } from '$lib/normalize/inline';
	import InlineView from '../InlineView.svelte';

	let { content }: { content: ProseContent } = $props();

	function paragraphs(): RichParagraph[] {
		return (content.paragraphs ?? []).map((p) =>
			typeof p === 'string' ? { children: asRichText(p) } : p
		);
	}
</script>

{#each paragraphs() as para}
	<p><InlineView nodes={para.children} /></p>
{/each}
