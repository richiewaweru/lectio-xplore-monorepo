<script lang="ts">
	import type { LectioSection } from '$lib/contract/document';
	import { buildRenderUnits } from '$lib/normalize/document';
	import BlockView from './BlockView.svelte';
	import HeadingBinding from './HeadingBinding.svelte';

	let { section }: { section: LectioSection } = $props();

	/**
	 * Array order is canonical after normalizeDocument.
	 * section.title renders exactly once as the section h2; nested heading blocks remain structural h3+.
	 */
	function numberedUnits() {
		let figureNumber = 0;
		return buildRenderUnits(section.blocks).map((unit) => {
			const lead = unit.kind === 'heading-binding' ? unit.lead : unit.block;
			const number = lead.object === 'figure' ? ++figureNumber : undefined;
			return { ...unit, figureNumber: number };
		});
	}

	const units = $derived(numberedUnits());
</script>

<section class="lectio-section" id={section.id}>
	<h2 class="lectio-section-title">{section.title}</h2>
	{#each units as unit (unit.kind === 'heading-binding' ? unit.heading.id : unit.block.id)}
		{#if unit.kind === 'heading-binding'}
			<HeadingBinding>
				<BlockView block={unit.heading} />
				<BlockView block={unit.lead} figureNumber={unit.figureNumber} />
			</HeadingBinding>
		{:else}
			<BlockView block={unit.block} figureNumber={unit.figureNumber} />
		{/if}
	{/each}
</section>
