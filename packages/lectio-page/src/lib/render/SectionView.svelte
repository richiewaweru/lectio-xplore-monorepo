<script lang="ts">
	import type { LectioSection } from '$lib/contract/document';
	import { buildRenderUnits } from '$lib/normalize/document';
	import BlockView from './BlockView.svelte';
	import HeadingBinding from './HeadingBinding.svelte';

	let { section }: { section: LectioSection } = $props();

	/**
	 * Array order is canonical after normalizeDocument.
	 * section.title is for contents/nav only — not rendered as a heading here.
	 */
	const units = $derived(buildRenderUnits(section.blocks));
</script>

<section class="lectio-section" id={section.id}>
	{#each units as unit (unit.kind === 'heading-binding' ? unit.heading.id : unit.block.id)}
		{#if unit.kind === 'heading-binding'}
			<HeadingBinding>
				<BlockView block={unit.heading} />
				<BlockView block={unit.lead} />
			</HeadingBinding>
		{:else}
			<BlockView block={unit.block} />
		{/if}
	{/each}
</section>
