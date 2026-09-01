<script lang="ts">
	import type { AsideContent } from '$lib/contract/document';
	import { asRichText } from '$lib/normalize/inline';
	import InlineView from '../InlineView.svelte';

	let { content, inMargin = false }: { content: AsideContent; inMargin?: boolean } = $props();
</script>

<aside class={['lectio-aside', inMargin && 'lectio-block--margin']}>
	{#if content.label}
		<strong>{content.label}</strong><br />
	{/if}
	<InlineView nodes={asRichText(content.body)} />
</aside>
