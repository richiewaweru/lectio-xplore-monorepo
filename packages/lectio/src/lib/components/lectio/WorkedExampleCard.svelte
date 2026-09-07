<script lang="ts">
	import type { DiagramContent, WorkedExampleContent, WorkedStep } from '$lib/schema/types';
	import { Card } from '$lib/components/ui/card';
	import { usePrintMode } from '$lib/utils/printContext';
	import { renderBlockMarkdown, renderInlineMarkdown } from '$lib/utils/markdown';
	import ExpandedSteps from '$lib/print/ExpandedSteps.svelte';
	import { Badge } from '$lib/components/ui/badge';
	import { Button } from '$lib/components/ui/button';
	import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '$lib/components/ui/collapsible';
	import {
		Accordion,
		AccordionItem,
		AccordionTrigger,
		AccordionContent
	} from '$lib/components/ui/accordion';
	import MathFormula from './MathFormula.svelte';
	import { sanitizeSvg } from '$lib/utils/sanitize';

	let {
		content,
		mode = 'step-reveal'
	}: {
		content: WorkedExampleContent;
		mode?: 'static' | 'step-reveal' | 'accordion';
	} = $props();

	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());

	let revealed = $state(0);

	const visibleSteps = $derived(
		mode === 'step-reveal' ? content.steps.slice(0, revealed) : content.steps
	);
	const isComplete = $derived(
		mode !== 'step-reveal' || content.steps.length === 0 || revealed >= content.steps.length
	);

	$effect(() => {
		revealed = mode === 'step-reveal' ? Math.min(1, content.steps.length) : content.steps.length;
	});

	function showNextStep() {
		revealed = Math.min(content.steps.length, revealed + 1);
	}
</script>

{#snippet inlineDiagram(diagram: DiagramContent)}
	<figure class="worked-example-inline-diagram" data-lectio-inline-diagram data-print-container="atomic">
		<div
			class="worked-example-inline-diagram-frame"
			role={diagram.image_url ? undefined : 'img'}
			aria-label={diagram.image_url ? undefined : diagram.alt_text}
		>
			{#if diagram.image_url}
				<img
					src={diagram.image_url}
					alt={diagram.alt_text}
					class="worked-example-inline-diagram-media"
					loading={printMode ? 'eager' : 'lazy'}
				/>
			{:else if diagram.svg_content}
				<div class="worked-example-inline-diagram-media">
					{@html sanitizeSvg(diagram.svg_content)}
				</div>
			{:else}
				<div class="worked-example-inline-diagram-empty">Diagram source unavailable.</div>
			{/if}
		</div>
		<figcaption class="worked-example-inline-diagram-caption">{diagram.caption}</figcaption>
	</figure>
{/snippet}

{#snippet stepBlock(step: WorkedStep, index: number)}
	<div class="flex gap-4">
		<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-violet-100 text-sm font-bold text-violet-700">
			{index + 1}
		</div>
		<div class="space-y-2">
			<p class="text-sm font-semibold uppercase tracking-[0.18em] text-violet-700">
				{step.label}
			</p>
			<div class="lectio-rich text-base leading-7 text-foreground/85">
				{@html renderBlockMarkdown(step.content)}
			</div>
			{#if step.formula}
				<div class="rounded-[1rem] bg-white/85 p-3 text-primary">
					<MathFormula formula={step.formula} displayMode />
				</div>
			{/if}
			{#if step.note}
				<p class="text-sm italic leading-6 text-muted-foreground">Note: {@html renderInlineMarkdown(step.note)}</p>
			{/if}
			{#if step.diagram_ref}
				<p class="text-xs font-semibold uppercase tracking-[0.16em] text-violet-700/75">
					Diagram reference: {step.diagram_ref}
				</p>
			{/if}
		</div>
	</div>
{/snippet}

{#snippet methodPreview(example: WorkedExampleContent)}
	<div class="rh-gap-component rh-radius-card bg-white/85 p-4">
		{#if example.method_label}
			<Badge variant="outline" class="border-violet-200 text-violet-700">
				{example.method_label}
			</Badge>
		{/if}
		<p class="text-sm leading-6 text-muted-foreground">{@html renderInlineMarkdown(example.setup)}</p>
		<div class="rh-gap-component">
			{#each example.steps as step, index}
				{@render stepBlock(step, index)}
			{/each}
		</div>
		<div class="rounded-[1rem] bg-violet-50 p-4 text-sm font-semibold leading-6 text-violet-950">
			{@html renderInlineMarkdown(example.conclusion)}
		</div>
	</div>
{/snippet}

{#if printMode}
	<div
		class="worked-example worked-example-print"
		data-print-container="itemized"
		data-print-has-media={content.diagram ? 'true' : 'false'}
	>
		<div class="worked-example__header">{content.title}</div>
		<p class="worked-example-print-setup">{@html renderInlineMarkdown(content.setup)}</p>
		{#if content.diagram}
			{@render inlineDiagram(content.diagram)}
		{/if}
		<ExpandedSteps steps={content.steps} title={content.title} />
		<p class="worked-example-print-conclusion">{@html renderInlineMarkdown(content.conclusion)}</p>
		{#if content.answer}
			<p class="worked-example-print-answer"><strong>Answer:</strong> {content.answer}</p>
		{/if}
		{#if content.alternative}
			<div class="worked-example-print-alternatives">
				<p class="worked-example-print-alt-heading"><strong>Alternative method</strong></p>
				{@render methodPreview(content.alternative)}
			</div>
		{/if}
		{#if content.alternatives?.length}
			<div class="worked-example-print-alternatives">
				<p class="worked-example-print-alt-heading"><strong>Other approaches</strong></p>
				<ul class="list-disc space-y-2 pl-5 text-sm leading-6">
					{#each content.alternatives as alternative}
						<li>{alternative}</li>
					{/each}
				</ul>
			</div>
		{/if}
	</div>
{:else}
<Card class="border-l-4 border-l-violet-500 bg-violet-50/45">
	<div class="space-y-5 rh-pad-card">
			<div class="rh-gap-component-tight">
				<div class="flex flex-wrap items-center rh-gap-cluster">
					<p class="eyebrow text-violet-600">Example</p>
					{#if content.method_label}
					<Badge variant="outline" class="border-violet-200 text-violet-700">
						{content.method_label}
					</Badge>
				{/if}
			</div>
			<h3 class="text-2xl font-semibold font-serif text-primary">{content.title}</h3>
			<p class="text-sm leading-6 text-muted-foreground">{@html renderInlineMarkdown(content.setup)}</p>
			{#if content.diagram}
				{@render inlineDiagram(content.diagram)}
			{/if}
		</div>

		{#if mode === 'accordion'}
			<Accordion type="single" class="rh-gap-component-tight">
				{#each content.steps as step, index}
					<AccordionItem value={`step-${index}`} class="bg-white/70">
						<AccordionTrigger>
							<span class="flex items-center rh-gap-cluster">
								<span class="flex h-7 w-7 items-center justify-center rounded-full bg-violet-100 text-xs font-bold text-violet-700">
									{index + 1}
								</span>
								{step.label}
							</span>
						</AccordionTrigger>
						<AccordionContent class="rh-gap-component-tight">
							{@render stepBlock(step, index)}
						</AccordionContent>
					</AccordionItem>
				{/each}
			</Accordion>
		{:else}
			<div class="rh-gap-component">
				{#each visibleSteps as step, index}
					<div class="animate-step-reveal">
						{@render stepBlock(step, index)}
					</div>
				{/each}
			</div>
		{/if}

		{#if mode === 'step-reveal' && revealed < content.steps.length}
			<Button variant="outline" class="w-fit" onclick={showNextStep}>
				Show next step
			</Button>
		{/if}

		<div class="rh-radius-card bg-white/85 p-4 text-sm font-semibold leading-7 text-primary">
			{@html renderInlineMarkdown(content.conclusion)}
		</div>

		{#if isComplete && content.answer}
			<div class="rh-radius-card bg-violet-100 p-4 text-sm leading-7 text-violet-950">
				<span class="mr-2 font-semibold uppercase tracking-[0.18em] text-violet-700">Answer:</span>
				{content.answer}
			</div>
		{/if}

		{#if isComplete && content.alternative}
			<Collapsible>
				<CollapsibleTrigger
					class="inline-flex h-9 items-center justify-center rounded-xl px-0 text-sm font-medium text-violet-700 transition-colors hover:text-violet-800"
				>
					Alternative method
				</CollapsibleTrigger>
				<CollapsibleContent class="pt-2">
					{@render methodPreview(content.alternative)}
				</CollapsibleContent>
			</Collapsible>
		{/if}

		{#if isComplete && content.alternatives?.length}
			<Collapsible>
				<CollapsibleTrigger
					class="inline-flex h-9 items-center justify-center rounded-xl px-0 text-sm font-medium text-violet-700 transition-colors hover:text-violet-800"
				>
					Other approaches
				</CollapsibleTrigger>
				<CollapsibleContent class="rh-radius-card bg-white/80 p-4 text-sm leading-6 text-foreground/82">
					<ul class="list-disc space-y-2 pl-5">
						{#each content.alternatives as alternative}
							<li>{alternative}</li>
						{/each}
					</ul>
				</CollapsibleContent>
			</Collapsible>
		{/if}
	</div>
</Card>
{/if}

<style>
	.worked-example-print {
		margin: 1rem 0;
	}

	.worked-example-print-setup {
		font-size: 0.875rem;
		color: #6b7280;
		margin-bottom: 1rem;
		line-height: 1.6;
	}

	.worked-example-print-alternatives {
		margin-top: 1rem;
		padding-top: 0.75rem;
		border-top: 1px solid #e5e7eb;
	}

	.worked-example-print-alt-heading {
		margin-bottom: 0.5rem;
		font-size: 0.875rem;
	}

	.worked-example-print-conclusion {
		padding: var(--rh-pad-card-tight) var(--rh-pad-card);
		border: 1px solid #e5e7eb;
		margin-top: 0.5rem;
		font-weight: 600;
		font-size: 0.875rem;
	}

	.worked-example-print-answer {
		margin-top: 0.75rem;
		font-size: 0.875rem;
	}

	.worked-example-inline-diagram {
		margin: 0.75rem 0;
		page-break-inside: avoid;
	}

	.worked-example-inline-diagram-frame {
		overflow: hidden;
		border: 1px solid hsl(var(--border) / 0.7);
		border-radius: 1rem;
		background: white;
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
	}

	.worked-example-inline-diagram-media {
		display: block;
		width: 100%;
		height: auto;
		object-fit: contain;
	}

	.worked-example-inline-diagram-frame :global(svg) {
		display: block;
		width: 100%;
		height: auto;
	}

	.worked-example-inline-diagram-caption {
		margin-top: 0.45rem;
		font-size: 0.875rem;
		line-height: 1.5;
		color: hsl(var(--muted-foreground));
	}

	.worked-example-inline-diagram-empty {
		display: flex;
		min-height: 7rem;
		align-items: center;
		justify-content: center;
		padding: 1rem;
		font-size: 0.875rem;
		color: hsl(var(--muted-foreground));
	}

	@media print {
		.worked-example-print {
			border: 1.5px solid #ccc;
			border-radius: 2px;
			padding: 1rem 1.25rem;
			page-break-inside: avoid;
		}

		.worked-example__header {
			display: flex;
			align-items: center;
			gap: 0.5rem;
			font-weight: 700;
			font-size: 1.05em;
			margin-bottom: 0.75rem;
			padding-bottom: 0.5rem;
			border-bottom: 1px solid #e2e2e2;
		}

		.worked-example__header::before {
			content: '✦';
			font-size: 0.9em;
		}

		:global(.worked-example-print .step) {
			display: flex;
			gap: 0.75rem;
			padding: 0.5rem 0;
		}

		:global(.worked-example-print .step-number) {
			flex-shrink: 0;
			width: 24px;
			height: 24px;
			border-radius: 50%;
			background: #333;
			color: #fff;
			font-size: 0.75em;
			font-weight: 700;
		}

		:global(.worked-example-print .step:nth-child(even)) {
			background: #fafafa;
			margin: 0 -0.5rem;
			padding-left: 0.5rem;
			padding-right: 0.5rem;
		}

		.worked-example-inline-diagram {
			margin: 0.5rem 0;
		}

		.worked-example-inline-diagram-frame {
			max-height: 150px;
		}

		.worked-example-inline-diagram-media {
			max-height: 150px;
		}

		.worked-example-inline-diagram-frame :global(svg) {
			max-height: 150px;
		}
	}
</style>
