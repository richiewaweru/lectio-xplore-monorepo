<script lang="ts">
	import { onMount } from 'svelte';
	import type { ArtifactProgress } from '$lib/types/units';
	import { PROGRESS_NOTE, formatElapsed, progressView } from './lesson-progress';

	interface Props {
		progress?: ArtifactProgress | null;
		/** Shown when the backend has not reported steps yet. */
		fallbackTitle?: string;
	}

	let { progress = null, fallbackTitle = 'Preparing your lesson' }: Props = $props();

	const view = $derived(progressView(progress));
	let nowMs = $state(Date.now());
	const elapsed = $derived(formatElapsed(view?.startedAt ?? null, nowMs));

	onMount(() => {
		const timer = setInterval(() => (nowMs = Date.now()), 1000);
		return () => clearInterval(timer);
	});
</script>

<section class="progress" data-testid="lesson-progress">
	<h2>{fallbackTitle}</h2>
	<p class="live">
		<span aria-live="polite" data-testid="lesson-progress-current">{#if view?.currentLabel}Now: {view.currentLabel}{:else}Getting started…{/if}</span>
		{#if elapsed}<span class="elapsed" data-testid="lesson-progress-elapsed"> · {elapsed}</span>{/if}
	</p>
	{#if view}
		<ol class="steps">
			{#each view.steps as step (step.key)}
				<li class={step.marker} aria-current={step.marker === 'active' ? 'step' : undefined}>
					<span class="mark" aria-hidden="true">
						{#if step.marker === 'done'}✓{:else if step.marker === 'failed'}!{:else if step.marker === 'active'}●{:else}○{/if}
					</span>
					<span class="text">{step.label} {step.counts}</span>
					<span class="sr-only">
						{step.marker === 'done' ? 'done' : step.marker === 'active' ? 'in progress' : step.marker === 'failed' ? 'needs attention' : 'waiting'}
					</span>
				</li>
			{/each}
		</ol>
		{#if view.figuresLine}<p class="figures" data-testid="lesson-progress-figures">{view.figuresLine}</p>{/if}
		{#each view.failedFigures as figure (figure.id)}
			<p class="figure-failed" data-testid="lesson-progress-figure-failed">
				{figure.sectionTitle}: {figure.summary}{#if figure.retryable} You can retry this.{/if}
			</p>
		{/each}
		{#if view.labelWarnings.length}<p class="note" data-testid="lesson-progress-warnings">Label check: {view.labelWarnings.join('; ')}</p>{/if}
	{/if}
	<p class="note">{PROGRESS_NOTE}</p>
</section>

<style>
	.progress {
		display: grid;
		gap: var(--space-2);
		padding: var(--space-4);
		border: 1px solid var(--rule);
		border-radius: var(--radius-lg);
		background: var(--surface);
		max-width: 34rem;
	}
	h2 {
		margin: 0;
		font-family: var(--font-serif);
		font-size: 1.15rem;
	}
	.live {
		margin: 0;
		color: var(--ink-2);
		font-size: 0.875rem;
	}
	.steps {
		list-style: none;
		margin: var(--space-2) 0 0;
		padding: 0;
		display: grid;
		gap: 0.4rem;
	}
	li {
		display: flex;
		gap: 0.6rem;
		align-items: baseline;
		color: var(--ink-3);
		font-size: 0.9rem;
	}
	li.active {
		color: var(--ink);
		font-weight: 600;
	}
	li.done {
		color: var(--ink-2);
	}
	li.failed {
		color: var(--danger);
	}
	.figures {
		margin: 0;
		color: var(--ink-2);
		font-size: 0.875rem;
	}
	.figure-failed {
		margin: 0;
		color: var(--danger);
		font-size: 0.8125rem;
	}
	.mark {
		width: 1rem;
		text-align: center;
	}
	.note {
		margin: var(--space-2) 0 0;
		color: var(--ink-3);
		font-size: 0.8125rem;
	}
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}
</style>
