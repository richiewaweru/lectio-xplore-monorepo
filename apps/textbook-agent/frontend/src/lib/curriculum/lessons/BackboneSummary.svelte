<script lang="ts">
	import type { LessonBackbone } from '$lib/types/backbone';

	interface Props {
		backbone: LessonBackbone;
	}

	let { backbone }: Props = $props();

	function show(value: unknown): string {
		if (value === null || value === undefined) return '';
		return typeof value === 'object' ? JSON.stringify(value) : String(value);
	}

	function entries(data: Record<string, unknown> | null | undefined): [string, unknown][] {
		return Object.entries(data ?? {});
	}
</script>

{#snippet dataList(data: Record<string, unknown>)}
	{#if entries(data).length}
		<dl class="data">
			{#each entries(data) as [key, value]}
				<dt>{key}</dt>
				<dd>{show(value)}</dd>
			{/each}
		</dl>
	{/if}
{/snippet}

<section class="backbone" aria-label="Lesson scenario and data">
	<p class="eyebrow">Lesson scenario and data</p>

	<div class="block">
		<p class="story">{backbone.anchor.story}</p>
		{@render dataList(backbone.anchor.data)}
		{#if backbone.anchor.answer}
			<p class="answer"><span>Answer:</span> {backbone.anchor.answer}</p>
		{/if}
	</div>

	{#if backbone.variants.length}
		<h4>Variants</h4>
		<ul class="variants">
			{#each backbone.variants as variant (variant.id)}
				<li class="block">
					<p class="story">{variant.change}</p>
					{@render dataList(variant.data)}
					{#if variant.answer}
						<p class="answer"><span>Answer:</span> {variant.answer}</p>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}

	{#if backbone.figures.length}
		<h4>Figures</h4>
		<ul class="figures">
			{#each backbone.figures as figure (figure.id)}
				<li class="block">
					<p class="story"><code>{figure.id}</code> {figure.purpose}</p>
					{#if figure.must_show.length}
						<p class="meta"><span>Must show:</span> {figure.must_show.join('; ')}</p>
					{/if}
					{#if figure.labels_required.length}
						<p class="meta"><span>Labels:</span> {figure.labels_required.join(', ')}</p>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</section>

<style>
	.backbone {
		display: grid;
		gap: var(--space-3);
		border: 1px solid var(--rule);
		border-radius: var(--radius-lg);
		background: var(--surface);
		padding: var(--space-4);
	}
	.eyebrow {
		margin: 0;
		color: var(--ink-3);
		font-size: 0.75rem;
		font-weight: 600;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}
	h4 {
		margin: 0;
		font-family: var(--font-serif);
		font-size: 1rem;
		font-weight: 600;
	}
	ul {
		display: grid;
		gap: var(--space-2);
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.block {
		border: 1px solid var(--rule);
		border-radius: var(--radius-md);
		padding: 0.75rem;
	}
	p {
		margin: 0 0 0.5rem;
		color: var(--ink-2);
		line-height: 1.5;
		font-size: 0.9rem;
	}
	.answer span,
	.meta span {
		font-weight: 600;
	}
	.data {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.25rem 0.75rem;
		margin: 0 0 0.5rem;
		font-size: 0.85rem;
	}
	dt {
		color: var(--ink-3);
	}
	dd {
		margin: 0;
		color: var(--ink-2);
		overflow-wrap: anywhere;
	}
</style>
