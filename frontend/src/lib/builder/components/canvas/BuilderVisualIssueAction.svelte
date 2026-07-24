<script lang="ts">
	import type { V3VisualBlock } from '$lib/api/v3';
	import type { BuilderIssue } from '$lib/builder/issues';
	import VisualRegeneratePopover from './VisualRegeneratePopover.svelte';

	let {
		issue,
		generationId,
		visual,
		onResolved = () => {},
		onRegenerated = async () => {}
	}: {
		issue: BuilderIssue;
		generationId: string | null;
		visual?: V3VisualBlock;
		onResolved?: (issue: BuilderIssue) => void;
		onRegenerated?: () => void | Promise<void>;
	} = $props();

</script>

{#if issue.visual_id}
	<div class="mt-2 w-full">
		{#if visual?.image_url}
			<img class="mb-2 h-24 w-24 rounded border object-cover" src={visual.image_url} alt={visual.qc_reasons?.join('; ') || 'Flagged generated image'} />
		{/if}
		<VisualRegeneratePopover
			presentation="inline"
			{generationId}
			{visual}
			onCompleted={() => onResolved(issue)}
			{onRegenerated}
		/>
	</div>
{/if}
