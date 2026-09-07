<script lang="ts">
	import type { MediaReference } from '$lib/teacher/document';
	import type { ImageBlockContent } from '$lib/schema/types';
	import { Card } from '$lib/components/ui/card';

	let {
		content,
		media = {}
	}: {
		content: ImageBlockContent;
		media?: Record<string, MediaReference>;
	} = $props();

	const ref = $derived(content.media_id ? media[content.media_id] : undefined);
	const isImage = $derived(ref?.type === 'image' && ref.url);

	const widthClass = $derived(
		(
			{
				full: 'w-full max-w-full',
				half: 'w-full max-w-[50%]',
				third: 'w-full max-w-[33.333333%]'
			} as const
		)[content.width ?? 'full']
	);

	const alignClass = $derived(
		(
			{
				left: 'mr-auto',
				center: 'mx-auto',
				right: 'ml-auto'
			} as const
		)[content.alignment ?? 'center']
	);

	const alt = $derived(
		(content.alt_text?.trim() || ref?.alt_text?.trim() || 'Lesson image') as string
	);
</script>

<Card
	class="border-primary/10 bg-white/88 rh-pad-card"
	data-print-container="atomic"
	data-print-has-media={isImage ? 'true' : 'false'}
>
	<div class="rh-gap-component-tight">
		<p class="eyebrow">Image</p>

		{#if isImage && ref}
			<figure class="space-y-2">
				<div
					class="{widthClass} {alignClass} block overflow-hidden rounded-[1rem] border border-border/70 bg-white shadow-[inset_0_1px_0_rgba(255,255,255,0.72)]"
				>
					<img src={ref.url} {alt} class="h-auto w-full object-contain" loading="lazy" />
				</div>
				{#if content.caption?.trim()}
					<figcaption class="text-center text-sm text-muted-foreground">{content.caption}</figcaption>
				{/if}
			</figure>
		{:else}
			<p class="text-sm text-muted-foreground">Image not available (upload an image in the editor).</p>
		{/if}
	</div>
</Card>
