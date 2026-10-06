<script lang="ts">
	import type { LessonApproachDraft } from '$lib/api/teaching-plan';
	import { Badge } from '$lib/ui';

	interface Props {
		draft: LessonApproachDraft;
	}

	let { draft }: Props = $props();

	const spine = $derived(draft.spine);
</script>

{#if spine}
	<section class="draft" aria-label="Teaching plan draft">
		<div class="head">
			<h3>{spine.learner_title}</h3>
			<Badge tone="info">Draft</Badge>
		</div>
		<p class="arc">{spine.arc}</p>
		<ol class="sections">
			{#each spine.sections as section (section.slot_id)}
				{@const ready = draft.sections[section.slot_id]}
				<li class="section" data-ready={ready ? 'true' : 'false'}>
					<p class="title">{section.display_title}</p>
					{#if section.specific_purpose}<p class="purpose">{section.specific_purpose}</p>{/if}
					{#if ready}
						<ul class="blocks">
							{#each ready.blocks as block, index (index)}
								<li class="block">
									<span class="intent">{block.intent}</span>
									<span class="brief">{block.brief}</span>
									{#if block.has_visual}<span class="figure">figure</span>{/if}
								</li>
							{/each}
						</ul>
					{:else}
						<p class="pending">Writing this section…</p>
					{/if}
				</li>
			{/each}
		</ol>
	</section>
{/if}

<style>
	.draft {
		display: grid;
		gap: var(--space-3);
		margin-top: var(--space-3);
	}
	.head {
		display: flex;
		align-items: center;
		gap: var(--space-2);
	}
	h3 {
		margin: 0;
		font-family: var(--font-serif);
		font-size: 1.15rem;
		font-weight: 600;
	}
	p {
		margin: 0;
		color: var(--ink-2);
		font-size: 0.9rem;
		line-height: 1.5;
	}
	.sections,
	.blocks {
		display: grid;
		gap: var(--space-2);
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.section {
		border: 1px solid var(--rule);
		border-radius: var(--radius-md);
		background: var(--surface);
		padding: 0.75rem;
	}
	.section[data-ready='false'] {
		opacity: 0.75;
	}
	.title {
		color: var(--ink-1, inherit);
		font-weight: 600;
	}
	.purpose,
	.pending {
		color: var(--ink-3);
	}
	.blocks {
		margin-top: 0.5rem;
	}
	.block {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.25rem 0.5rem;
		font-size: 0.85rem;
		color: var(--ink-2);
	}
	.intent {
		font-weight: 600;
	}
	.figure {
		border: 1px solid var(--rule);
		border-radius: var(--radius-md);
		padding: 0 0.35rem;
		color: var(--ink-3);
		font-size: 0.7rem;
		text-transform: uppercase;
	}
</style>
