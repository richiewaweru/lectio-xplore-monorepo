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
			{#each spine.sections as section, index (section.slot_id)}
				{@const ready = draft.sections[section.slot_id]}
				<li class="card" data-ready={ready ? 'true' : 'false'}>
					<span class="num" aria-hidden="true">{index + 1}</span>
					<div class="body">
						<h4>{section.display_title?.trim() || section.specific_purpose?.trim() || `Section ${index + 1}`}</h4>
						{#if section.specific_purpose?.trim()}<p class="purpose">{section.specific_purpose}</p>{/if}
						{#if ready}
							<ul class="blocks">
								{#each ready.blocks as block, blockIndex (blockIndex)}
									<li class="block">
										<span class="brief">{block.brief}</span>
										{#if block.has_visual}<span class="figure">figure</span>{/if}
									</li>
								{/each}
							</ul>
						{:else}
							<p class="pending">Writing this section…</p>
						{/if}
					</div>
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
	h4 {
		margin: 0;
		font-size: 1rem;
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
	.card {
		display: flex;
		gap: 0.75rem;
		border: 1px solid var(--rule);
		border-radius: var(--radius-md);
		background: var(--surface);
		padding: 0.75rem;
	}
	.card[data-ready='false'] {
		opacity: 0.75;
	}
	.num {
		flex: none;
		display: grid;
		place-items: center;
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 999px;
		border: 1px solid var(--rule);
		color: var(--ink-2);
		font-size: 0.85rem;
		font-weight: 600;
	}
	.body {
		display: grid;
		gap: 0.35rem;
		min-width: 0;
	}
	.purpose,
	.pending {
		color: var(--ink-3);
	}
	.block {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.25rem 0.5rem;
		font-size: 0.85rem;
		color: var(--ink-2);
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
