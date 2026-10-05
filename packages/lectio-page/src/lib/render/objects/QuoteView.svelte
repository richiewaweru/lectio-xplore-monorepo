<script lang="ts">
	import type { QuoteContent } from '$lib/contract/document';
	import { asRichText } from '$lib/normalize/inline';
	import InlineView from '../InlineView.svelte';

	let { content }: { content: QuoteContent } = $props();
</script>

<blockquote class="lectio-quote">
	<p><InlineView nodes={asRichText(content.text)} /></p>
	{#if content.attribution}<cite><InlineView nodes={asRichText(content.attribution)} /></cite>{/if}
</blockquote>
