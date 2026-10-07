<script lang="ts">
	import type { LessonBackbone } from '$lib/types/backbone';
	import BackboneSummary from './BackboneSummary.svelte';
	import TeachingPlanReview from './TeachingPlanReview.svelte';
	import type {
		TeachingPlanIdentityView,
		TeachingPlanView,
		TeachingReviewView
	} from './teaching-plan-review';
	import {
		resolveMisconceptions,
		sectionFigureNotes,
		sectionLearnerActions,
		sectionTitle,
		type MisconceptionView
	} from './teaching-plan-teacher';

	interface Props {
		plan: TeachingPlanView;
		review?: TeachingReviewView;
		identity?: TeachingPlanIdentityView;
		misconceptions?: MisconceptionView[];
		backbone?: LessonBackbone | null;
	}

	let { plan, review, identity, misconceptions = [], backbone = null }: Props = $props();

	let showFull = $state(false);

	const sections = $derived(plan.sections ?? []);
	const focus = $derived(resolveMisconceptions(plan.misconception_focus_ids, misconceptions));
	const startingState = $derived((plan.starting_state ?? []).filter((item) => item?.trim()));
	const targetState = $derived((plan.target_state ?? []).filter((item) => item?.trim()));
</script>

<article class="teacher" aria-label="Lesson plan overview">
	<header>
		<p class="eyebrow">This lesson</p>
		<h3>{plan.learner_title?.trim() || 'Lesson plan'}</h3>
		{#if plan.arc?.trim()}<p class="arc">{plan.arc}</p>{/if}
	</header>

	{#if targetState.length}
		<div class="group">
			<p class="label">By the end, learners can…</p>
			<ul>{#each targetState as item}<li>{item}</li>{/each}</ul>
		</div>
	{/if}

	{#if startingState.length}
		<details class="group">
			<summary>They start from…</summary>
			<ul>{#each startingState as item}<li>{item}</li>{/each}</ul>
		</details>
	{/if}

	{#if backbone?.anchor?.story}
		<div class="group">
			<p class="label">The example we'll use</p>
			<p>{backbone.anchor.story}</p>
		</div>
	{/if}

	{#if focus.length}
		<div class="group">
			<p class="label">Misconceptions we'll tackle</p>
			<ul>
				{#each focus as item (item.id)}
					<li>{item.description}{#if item.risk}<span class="risk"> ({item.risk} risk)</span>{/if}</li>
				{/each}
			</ul>
		</div>
	{/if}

	<ol class="sections" aria-label="Lesson sections">
		{#each sections as section, index (section.slot_id)}
			{@const actions = sectionLearnerActions(section.blocks)}
			{@const figures = sectionFigureNotes(section.blocks)}
			<li class="card">
				<span class="num" aria-hidden="true">{index + 1}</span>
				<div class="body">
					<h4>{sectionTitle(section, index)}</h4>
					{#if section.specific_purpose?.trim()}
						<p><span class="label">What happens</span> {section.specific_purpose}</p>
					{/if}
					{#if actions.length}
						<p><span class="label">Learners will</span> {actions.join('; ')}</p>
					{/if}
					{#each figures as figure}
						<p class="note">Figure: {figure}</p>
					{/each}
					{#each (section.blocks ?? []).filter((b) => b.departure_reason?.trim()) as block (block.id)}
						<p class="note">{block.departure_reason}</p>
					{/each}
				</div>
			</li>
		{/each}
	</ol>

	<button type="button" class="toggle" aria-expanded={showFull} onclick={() => (showFull = !showFull)}>
		{showFull ? 'Hide full plan' : 'Inspect full plan'}
	</button>
	{#if showFull}
		<div class="full">
			{#if backbone}<BackboneSummary {backbone} />{/if}
			<TeachingPlanReview {plan} {review} {identity} />
		</div>
	{/if}
</article>

<style>
	.teacher {
		display: grid;
		gap: var(--space-3);
	}
	h3 {
		margin: 0;
		font-family: var(--font-serif);
		font-size: 1.25rem;
		font-weight: 600;
	}
	h4 {
		margin: 0;
		font-size: 1rem;
		font-weight: 600;
	}
	p,
	ul {
		margin: 0;
		color: var(--ink-2);
		font-size: 0.9rem;
		line-height: 1.5;
	}
	ul {
		padding-left: 1.1rem;
	}
	.eyebrow,
	.label {
		color: var(--ink-3);
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.group {
		display: grid;
		gap: 0.25rem;
	}
	summary {
		cursor: pointer;
		color: var(--ink-3);
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.risk,
	.note {
		color: var(--ink-3);
	}
	.note {
		font-size: 0.8rem;
		font-style: italic;
	}
	.sections {
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
	.toggle {
		justify-self: start;
		background: none;
		border: 0;
		padding: 0;
		color: var(--ink-2);
		font: inherit;
		font-size: 0.85rem;
		text-decoration: underline;
		cursor: pointer;
	}
	.full {
		display: grid;
		gap: var(--space-3);
	}
</style>
