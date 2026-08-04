<script lang="ts">
	const previews = {
		'guided-concept-path': {
			name: 'Guided Concept Path',
			summary:
				'A first-exposure calculus section that shows the full scaffold from hook to worked example to practice.',
			title: 'Why does calculus exist?',
			headline: 'How fast is something moving at this exact instant?'
		},
		'formal-track': {
			name: 'Formal Track',
			summary: 'A rigorous single-column presentation for proof-oriented content.',
			title: 'Limit laws as a formal system',
			headline: 'Why formal steps matter when intuition stops helping.'
		}
	} as const;

	let {
		templateId,
		presetId = null,
		showMetadata = true
	}: {
		templateId: string;
		presetId?: string | null;
		showMetadata?: boolean;
	} = $props();

	const preview = $derived(previews[templateId as keyof typeof previews] ?? null);
</script>

<div data-testid="template-preview-surface" data-preset={presetId ?? ''}>
	{#if preview}
		{#if showMetadata}
			<h2>{preview.name}</h2>
		{/if}
		<p>{preview.summary}</p>
		<p>{preview.title}</p>
		<p>{preview.headline}</p>
		<p>{presetId === 'blue-classroom' ? 'Blue Classroom navy, sky, parchment' : 'Default preset'}</p>
	{:else}
		<p>Preview unavailable for: {templateId}</p>
	{/if}
</div>
