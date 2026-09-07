<script lang="ts">
	import PracticeStack from '$lib/components/lectio/PracticeStack.svelte';
	import type { PracticeContent } from '$lib/schema/types';
	import { providePrintMode } from '$lib/utils/printContext';

	let {
		content,
		showInlineAnswersInPrint = false
	}: {
		content: PracticeContent;
		showInlineAnswersInPrint?: boolean;
	} = $props();

	providePrintMode(() => true);
</script>

<PracticeStack {content} {showInlineAnswersInPrint} />
