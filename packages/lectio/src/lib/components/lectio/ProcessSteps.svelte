<script lang="ts">
	import type { ProcessContent } from '$lib/schema/types';
	import { Button } from '$lib/components/ui/button';
	import { Card } from '$lib/components/ui/card';
	import { usePrintMode } from '$lib/utils/printContext';
	import Checkboxes from '$lib/print/Checkboxes.svelte';
	import { renderInlineMarkdown } from '$lib/utils/markdown';

	let {
		content,
		mode = 'static'
	}: { content: ProcessContent; mode?: 'static' | 'step-reveal' } = $props();

	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());

	let visibleSteps = $state(0);

	$effect(() => {
		visibleSteps = mode === 'step-reveal' ? Math.min(1, content.steps.length) : content.steps.length;
	});

	const renderedSteps = $derived(
		mode === 'step-reveal' ? content.steps.slice(0, visibleSteps) : content.steps
	);

	function formatInputOutput(step: ProcessContent['steps'][number]) {
		const pieces: string[] = [];

		if (step.input) {
			pieces.push(`Input: ${step.input}`);
		}

		if (step.output) {
			pieces.push(`Output: ${step.output}`);
		}

		return pieces.join('  ');
	}
</script>

{#if printMode}
	<div class="process-print" data-print-container="itemized">
		<h4 class="process-print-title">{content.title}</h4>
		{#if content.intro}
			<p class="process-print-intro">{content.intro}</p>
		{/if}
		<div class="process-print-steps-layout">
			<div class="process-print-checkboxes">
				<Checkboxes count={content.steps.length} />
			</div>
			<div class="process-print-steps">
				{#each content.steps as step}
					<div class="process-print-step" data-print-item="process-step">
						<div class="process-print-step-number">{step.number}</div>
						<div class="process-print-step-content">
							<div class="process-print-action">{step.action}</div>
							<div class="process-print-detail">{@html renderInlineMarkdown(step.detail)}</div>
							{#if step.warning}
								<div class="process-print-warning">Warning: {step.warning}</div>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		</div>
	</div>
{:else}
<Card class="border-emerald-200 bg-emerald-50/45 rh-pad-card">
	<div class="rh-gap-component">
		<div class="space-y-2">
			<p class="eyebrow text-emerald-700">Process</p>
			<h3 class="text-2xl font-semibold font-serif text-primary">{content.title}</h3>
			{#if content.intro}
				<p class="text-sm leading-6 text-muted-foreground">{@html renderInlineMarkdown(content.intro)}</p>
			{/if}
		</div>

		{#each renderedSteps as step}
			<div class="rh-radius-card border border-emerald-100 bg-white/82 p-4">
				<div class="flex items-start gap-4">
					<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-sm font-bold text-emerald-700">
						{step.number}
					</div>
					<div class="space-y-2">
						<p class="text-sm font-semibold uppercase tracking-[0.18em] text-emerald-700">
							{step.action}
						</p>
						<p class="text-base leading-7 text-foreground/84">{@html renderInlineMarkdown(step.detail)}</p>
						{#if step.input || step.output}
							<p class="text-xs uppercase tracking-[0.16em] text-muted-foreground">
								{formatInputOutput(step)}
							</p>
						{/if}
						{#if step.warning}
							<p class="text-sm italic leading-6 text-amber-800">Watch for: {step.warning}</p>
						{/if}
					</div>
				</div>
			</div>
		{/each}

		{#if mode === 'step-reveal' && visibleSteps < content.steps.length}
			<Button
				variant="outline"
				onclick={() => (visibleSteps = Math.min(visibleSteps + 1, content.steps.length))}
			>
				Show next step
			</Button>
		{/if}
	</div>
</Card>
{/if}

<style>
	.process-print {
		margin: 1rem 0;
	}

	.process-print-title {
		font-size: 1.125rem;
		font-weight: 600;
		margin-bottom: 0.5rem;
	}

	.process-print-intro {
		font-size: 0.875rem;
		color: #6b7280;
		margin-bottom: 1rem;
	}

	.process-print-steps-layout {
		display: flex;
		gap: 1rem;
	}

	.process-print-checkboxes {
		flex-shrink: 0;
	}

	.process-print-steps {
		flex: 1;
	}

	.process-print-step {
		display: flex;
		gap: 1rem;
		margin-bottom: 1.5rem;
		page-break-inside: avoid;
	}

	.process-print-step-number {
		flex-shrink: 0;
		width: 1.5rem;
		height: 1.5rem;
		border-radius: 50%;
		background: #e5e7eb;
		display: flex;
		align-items: center;
		justify-content: center;
		font-weight: 600;
		font-size: 0.875rem;
	}

	.process-print-step-content {
		flex: 1;
	}

	.process-print-action {
		font-weight: 600;
		margin-bottom: 0.25rem;
	}

	.process-print-detail {
		line-height: 1.6;
		font-size: 0.875rem;
	}

	.process-print-warning {
		margin-top: 0.5rem;
		font-size: 0.875rem;
		color: #d97706;
	}
</style>
