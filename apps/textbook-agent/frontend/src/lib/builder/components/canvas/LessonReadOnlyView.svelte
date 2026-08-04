<script lang="ts">
	import { basePresetMap, LectioThemeSurface } from 'lectio';
	import type { LessonDocument } from 'lectio';
	import BlockPreview from './BlockPreview.svelte';

	let { document: doc }: { document: LessonDocument } = $props();

	const preset = $derived(basePresetMap[doc.preset_id] ?? null);
	const sections = $derived([...doc.sections].sort((a, b) => a.position - b.position));
</script>

{#if preset}
	<LectioThemeSurface {preset}>
		{#snippet children()}
			<div class="lesson-read-only space-y-6" data-testid="lesson-read-only">
				{#each sections as section (section.id)}
					<section class="read-only-section">
						<h2 class="mb-4 border-b border-slate-200 pb-2 text-lg font-semibold text-slate-900">
							{section.title}
						</h2>
						{#each section.block_ids as bid (bid)}
							{@const block = doc.blocks[bid]}
							{#if block}
								<div class="block-content mb-6">
									<BlockPreview
										componentId={block.component_id}
										content={block.content}
										media={doc.media}
									/>
								</div>
							{/if}
						{/each}
					</section>
				{/each}
			</div>
		{/snippet}
	</LectioThemeSurface>
{:else}
	<div class="lesson-read-only text-amber-800" data-testid="lesson-read-only">
		<p class="text-sm">Unknown preset "{doc.preset_id}".</p>
		{#each sections as section (section.id)}
			<h2 class="mb-2 mt-6 font-semibold">{section.title}</h2>
			{#each section.block_ids as bid (bid)}
				{@const block = doc.blocks[bid]}
				{#if block}
					<div class="block-content mb-6">
						<BlockPreview
							componentId={block.component_id}
							content={block.content}
							media={doc.media}
						/>
					</div>
				{/if}
			{/each}
		{/each}
	</div>
{/if}
