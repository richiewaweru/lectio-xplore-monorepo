<script lang="ts">
	import V3CanvasSection from '$lib/components/studio/V3CanvasSection.svelte';
	import type { CanvasSection, V3Stage } from '$lib/types/v3';

	interface Props {
		sections: CanvasSection[];
		stage: V3Stage;
		templateId: string;
	}

	let { sections, stage, templateId }: Props = $props();

	const progressLabel: Record<string, string> = {
		fill: 'Writing your resource...',
		edit: 'Resource ready'
	};
</script>

<div class="v3-canvas mx-auto max-w-3xl space-y-6 px-4 py-6">
	<div class="text-center text-sm text-muted-foreground" role="status" aria-live="polite">
		{progressLabel[stage] ?? ''}
	</div>

	<div class="space-y-8">
		{#each sections as section (section.id)}
			<V3CanvasSection {section} {templateId} />
		{/each}
	</div>
</div>
