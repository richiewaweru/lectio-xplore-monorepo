<script lang="ts">
	import WorkedExampleCard from '$lib/components/lectio/WorkedExampleCard.svelte';
	import type { WorkedExampleContent } from '$lib/schema/types';
	import { providePrintMode } from '$lib/utils/printContext';

	let { content }: { content: WorkedExampleContent } = $props();

	providePrintMode(() => true);
</script>

<WorkedExampleCard {content} />
