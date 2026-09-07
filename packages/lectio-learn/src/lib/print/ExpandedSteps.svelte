<script lang="ts">
	import type { WorkedStep } from '$lib/schema/types';
	import { renderBlockMarkdown, renderInlineMarkdown } from '$lib/utils/markdown';

	let {
		steps,
		title = undefined
	}: { steps: WorkedStep[]; title?: string } = $props();
</script>

<div class="expanded-steps">
	{#if title}
		<h4 class="steps-title">{title}</h4>
	{/if}

	{#each steps as step, idx}
		<div class="step worked-step-print" data-print-item="worked-step">
			<div class="step-number">{idx + 1}</div>
			<div class="step-content">
				<div class="step-label">{step.label}</div>
				<div class="step-detail lectio-rich">{@html renderBlockMarkdown(step.content)}</div>
				{#if step.note}
					<div class="step-note">{@html renderInlineMarkdown(step.note)}</div>
				{/if}
			</div>
		</div>
	{/each}
</div>

<style>
	.expanded-steps {
		margin: 1rem 0;
	}

	.steps-title {
		font-size: 1.125rem;
		font-weight: 600;
		margin-bottom: 1rem;
	}

	.step {
		display: flex;
		gap: 1rem;
		margin-bottom: 1.5rem;
		page-break-inside: avoid;
	}

	.step-number {
		flex-shrink: 0;
		width: 2rem;
		height: 2rem;
		border-radius: 50%;
		background: #1f2937;
		color: white;
		display: flex;
		align-items: center;
		justify-content: center;
		font-weight: 600;
		font-size: 0.875rem;
	}

	.step-content {
		flex: 1;
	}

	.step-label {
		font-weight: 600;
		margin-bottom: 0.5rem;
	}

	.step-detail {
		margin-bottom: 0.5rem;
		line-height: 1.6;
	}

	.step-note {
		font-size: 0.875rem;
		font-style: italic;
		color: #6b7280;
	}

	@media print {
		.step-number {
			background: #000;
		}
	}
</style>
