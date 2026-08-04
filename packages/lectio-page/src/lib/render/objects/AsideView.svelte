<script lang="ts">
	import type { AsideContent } from '$lib/contract/document';
	import { asRichText } from '$lib/normalize/inline';
	import InlineView from '../InlineView.svelte';

	let { content }: { content: AsideContent } = $props();
</script>

<aside class="lectio-aside">
	{#if content.label}
		<strong>{content.label}</strong><br />
	{/if}
	<InlineView nodes={asRichText(content.body)} />
</aside>
