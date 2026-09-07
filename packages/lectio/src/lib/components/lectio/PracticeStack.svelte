<script lang="ts">
	import type { DiagramContent, PracticeContent } from '$lib/schema/types';
	import { Card } from '$lib/components/ui/card';
	import { usePrintMode } from '$lib/utils/printContext';
	import RuledLines from '$lib/print/RuledLines.svelte';
	import {
		Accordion,
		AccordionItem,
		AccordionTrigger,
		AccordionContent
	} from '$lib/components/ui/accordion';
	import { Badge } from '$lib/components/ui/badge';
	import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '$lib/components/ui/collapsible';
	import { Button } from '$lib/components/ui/button';
	import { renderBlockMarkdown } from '$lib/utils/markdown';
	import { sanitizeSvg } from '$lib/utils/sanitize';

	type PracticeStackMode = 'accordion' | 'flat-list';
	type SelfAssessment = 'matched' | 'review';

let {
		content,
		mode = 'accordion',
		showInlineAnswersInPrint = false
	}: {
		content: PracticeContent;
		mode?: PracticeStackMode;
		showInlineAnswersInPrint?: boolean;
	} = $props();

	const difficultyConfig: Record<string, { label: string; className: string }> = {
		warm: { label: 'Warm', className: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
		medium: { label: 'Medium', className: 'bg-amber-50 text-amber-700 border-amber-200' },
		cold: { label: 'Cold', className: 'bg-blue-50 text-blue-700 border-blue-200' },
		extension: { label: 'Extension', className: 'bg-purple-50 text-purple-700 border-purple-200' }
	};

	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());

	let hintsRevealed = $state<Record<number, number>>({});
	let selfAssessments = $state<Record<number, SelfAssessment>>({});

	function revealNextHint(index: number, total: number) {
		const current = hintsRevealed[index] ?? 0;
		if (current < total) {
			hintsRevealed[index] = current + 1;
		}
	}

	function setAssessment(index: number, value: SelfAssessment) {
		selfAssessments[index] = value;
	}
</script>

{#snippet inlineDiagram(diagram: DiagramContent)}
	<figure class="practice-inline-diagram" data-lectio-inline-diagram>
		<div
			class="practice-inline-diagram-frame"
			role={diagram.image_url ? undefined : 'img'}
			aria-label={diagram.image_url ? undefined : diagram.alt_text}
		>
			{#if diagram.image_url}
				<img
					src={diagram.image_url}
					alt={diagram.alt_text}
					class="practice-inline-diagram-media"
					loading={printMode ? 'eager' : 'lazy'}
				/>
			{:else if diagram.svg_content}
				<div class="practice-inline-diagram-media">
					{@html sanitizeSvg(diagram.svg_content)}
				</div>
			{:else}
				<div class="practice-inline-diagram-empty">Diagram source unavailable.</div>
			{/if}
		</div>
		<figcaption class="practice-inline-diagram-caption">{diagram.caption}</figcaption>
	</figure>
{/snippet}

{#if printMode}
	<div
		class="practice-print"
		data-lectio-block="practice"
		data-print-container="itemized"
		data-print-show-inline-answers={showInlineAnswersInPrint ? 'true' : 'false'}
	>
		<h4 class="practice-print-title">{content.label ?? 'Review Exercises'}</h4>
		{#each content.problems as problem, idx}
			<div class="practice-print-problem" data-print-item="practice-problem">
				<div class="practice-print-header">
					<span class="practice-print-number">Problem {idx + 1}</span>
					<span class="practice-print-difficulty">{problem.difficulty}</span>
				</div>
				{#if problem.context}
					<p class="practice-print-context">{problem.context}</p>
				{/if}
				{#if problem.diagram}
					{@render inlineDiagram(problem.diagram)}
				{/if}
				<div class="practice-print-question lectio-rich">{@html renderBlockMarkdown(problem.question)}</div>
				{#if problem.hints?.length}
					<div class="practice-print-hints">
						<p class="practice-print-hints-label"><strong>Hints:</strong></p>
						{#each problem.hints as hint}
							<div class="practice-print-hint lectio-rich">{@html renderBlockMarkdown(hint.text)}</div>
						{/each}
					</div>
				{/if}
				{#if problem.writein_lines && problem.writein_lines > 0}
					<div data-print-role="answer-lines">
						<RuledLines lines={problem.writein_lines} label="Your answer:" />
					</div>
				{/if}
				{#if problem.solution && content.solutions_available && showInlineAnswersInPrint}
					<div class="practice-print-solution" data-print-role="inline-answer">
						<div class="lectio-rich">
							<strong>Solution:</strong> {@html renderBlockMarkdown(problem.solution.approach)}
						</div>
						<div class="practice-print-answer lectio-rich">
							<strong>Answer:</strong> {@html renderBlockMarkdown(problem.solution.answer)}
						</div>
					</div>
				{/if}
			</div>
		{/each}
	</div>
{:else}
<Card class="border-primary/10 bg-white/88 rh-pad-card" data-lectio-block="practice">
	<div class="rh-gap-component">
		<div class="space-y-2">
			<p class="eyebrow text-amber-600">{content.label ?? 'Practice problems'}</p>
			<p class="text-sm leading-6 text-muted-foreground">
				{mode === 'accordion'
					? 'Open one problem at a time, reveal hints progressively, and only expand the worked solution if it is needed.'
					: 'Keep every problem visible, reveal hints progressively, and check your own work without losing your place.'}
			</p>
		</div>

		{#snippet problemBody(problem: PracticeContent['problems'][number], index: number)}
			{@const shown = hintsRevealed[index] ?? 0}
			{@const assessment = selfAssessments[index]}

			{#if problem.context}
				<div class="rounded-xl bg-muted/45 p-3 text-sm leading-6 text-muted-foreground">
					Context: {problem.context}
				</div>
			{/if}

			{#if problem.diagram}
				{@render inlineDiagram(problem.diagram)}
			{/if}

			<div class="rh-gap-component-tight">
				{#each problem.hints.slice(0, shown) as hint}
					<div class="rounded-xl bg-muted/55 p-3 text-sm leading-relaxed text-muted-foreground">
						<p class="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-foreground/60">
							Hint {hint.level} of {problem.hints.length}
						</p>
						<div class="lectio-rich">{@html renderBlockMarkdown(hint.text)}</div>
					</div>
				{/each}

				{#if shown < problem.hints.length}
					<Button
						variant="ghost"
						size="sm"
						class="h-7 px-0 text-xs text-muted-foreground"
						onclick={() => revealNextHint(index, problem.hints.length)}
					>
						{shown === 0 ? 'Show hint' : 'Show next hint'}
					</Button>
				{/if}
			</div>

			{#if problem.solution}
				<Collapsible class="mt-2">
					<CollapsibleTrigger
						class="inline-flex h-7 items-center justify-center rounded-xl px-0 text-xs font-medium text-emerald-700 transition-colors hover:bg-accent hover:text-emerald-800"
					>
						Show answer
					</CollapsibleTrigger>
					<CollapsibleContent>
						<div class="mt-2 rounded-xl bg-emerald-50 p-3 text-sm font-medium leading-relaxed text-emerald-800">
							<div class="lectio-rich">{@html renderBlockMarkdown(problem.solution.answer)}</div>
						</div>

						<Collapsible class="mt-2">
							<CollapsibleTrigger
								class="inline-flex h-7 items-center justify-center rounded-xl px-0 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
							>
								Show worked solution
							</CollapsibleTrigger>
							<CollapsibleContent>
								<div class="mt-2 rounded-xl bg-muted/50 p-3 text-sm leading-relaxed text-muted-foreground">
									<p class="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-foreground/60">
										Approach
									</p>
									<div class="lectio-rich">{@html renderBlockMarkdown(problem.solution.approach)}</div>
									{#if problem.solution.worked}
										<div class="lectio-rich mt-3">{@html renderBlockMarkdown(problem.solution.worked)}</div>
									{/if}
								</div>
							</CollapsibleContent>
						</Collapsible>
					</CollapsibleContent>
				</Collapsible>
			{/if}

			{#if problem.self_assess}
				<div class="rounded-xl border border-border/70 bg-background/80 p-4">
					<p class="text-sm font-semibold text-primary">Self-check</p>
					<p class="mt-1 text-sm leading-6 text-muted-foreground">
						Compare your work to the answer and mark how it went.
					</p>
					<div class="mt-3 flex flex-wrap gap-2">
						<Button
							variant={assessment === 'matched' ? 'default' : 'outline'}
							size="sm"
							onclick={() => setAssessment(index, 'matched')}
						>
							Matched
						</Button>
						<Button
							variant={assessment === 'review' ? 'default' : 'outline'}
							size="sm"
							onclick={() => setAssessment(index, 'review')}
						>
							Needs review
						</Button>
					</div>
				</div>
			{/if}

			{#if problem.writein_lines && problem.writein_lines > 0}
				<div class="rh-gap-component-tight rounded-xl border border-dashed border-border/80 bg-background/70 p-4">
					{#each Array.from({ length: problem.writein_lines }) as _}
						<div class="h-6 border-b border-border/70"></div>
					{/each}
				</div>
			{/if}
		{/snippet}

		{#if mode === 'accordion'}
			<Accordion type="single" class="space-y-2">
				{#each content.problems as problem, i}
					{@const diff = difficultyConfig[problem.difficulty] ?? difficultyConfig.medium}
					<AccordionItem value={`problem-${i}`} class="rounded-xl border bg-card px-4">
						<AccordionTrigger class="py-4 hover:no-underline">
							<div class="flex items-start rh-gap-cluster text-left">
								<Badge variant="outline" class={diff.className}>{diff.label}</Badge>
								<div>
									{#if problem.context}
										<div class="mb-1 text-xs italic text-muted-foreground">{problem.context}</div>
									{/if}
									<div class="lectio-rich text-sm leading-relaxed">
										{@html renderBlockMarkdown(problem.question)}
									</div>
								</div>
							</div>
						</AccordionTrigger>

						<AccordionContent class="rh-gap-component pb-4">
							{@render problemBody(problem, i)}
						</AccordionContent>
					</AccordionItem>
				{/each}
			</Accordion>
		{:else}
			<div class="rh-gap-component">
				{#each content.problems as problem, i}
					{@const diff = difficultyConfig[problem.difficulty] ?? difficultyConfig.medium}
					<div class="rounded-xl border bg-card p-4">
						<div class="mb-4 flex items-start rh-gap-cluster">
							<Badge variant="outline" class={diff.className}>{diff.label}</Badge>
							<div>
								{#if problem.context}
									<div class="mb-1 text-xs italic text-muted-foreground">{problem.context}</div>
								{/if}
								<div class="lectio-rich text-sm leading-relaxed">
									{@html renderBlockMarkdown(problem.question)}
								</div>
							</div>
						</div>

						<div class="rh-gap-component">
							{@render problemBody(problem, i)}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</Card>
{/if}

<style>
	.practice-inline-diagram {
		margin: 0.75rem 0;
		page-break-inside: avoid;
	}

	.practice-inline-diagram-frame {
		overflow: hidden;
		border: 1px solid hsl(var(--border) / 0.7);
		border-radius: 1rem;
		background: white;
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
	}

	.practice-inline-diagram-media {
		display: block;
		width: 100%;
		height: auto;
		object-fit: contain;
	}

	.practice-inline-diagram-frame :global(svg) {
		display: block;
		width: 100%;
		height: auto;
	}

	.practice-inline-diagram-caption {
		margin-top: 0.45rem;
		font-size: 0.875rem;
		line-height: 1.5;
		color: hsl(var(--muted-foreground));
	}

	.practice-inline-diagram-empty {
		display: flex;
		min-height: 7rem;
		align-items: center;
		justify-content: center;
		padding: 1rem;
		font-size: 0.875rem;
		color: hsl(var(--muted-foreground));
	}

	@media print {
		.practice-inline-diagram {
			margin: 0.5rem 0;
		}

		.practice-inline-diagram-frame {
			max-height: 150px;
		}

		.practice-inline-diagram-media {
			max-height: 150px;
		}

		.practice-inline-diagram-frame :global(svg) {
			max-height: 150px;
		}
	}
	.practice-print {
		margin: 1rem 0;
	}

	.practice-print-title {
		font-weight: 700;
		font-size: 0.85em;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		padding-bottom: 0.4rem;
		border-bottom: 2px solid #333;
		margin-bottom: 1rem;
	}

	.practice-print-problem {
		page-break-inside: avoid;
		margin-bottom: var(--rh-gap-section);
		padding: var(--rh-pad-card);
		border: 1px solid #e5e7eb;
	}

	.practice-print-header {
		display: flex;
		justify-content: space-between;
		margin-bottom: 0.75rem;
	}

	.practice-print-number {
		font-weight: 600;
	}

	.practice-print-difficulty {
		font-size: 0.875rem;
		color: #6b7280;
		text-transform: capitalize;
	}

	.practice-print-context {
		font-size: 0.875rem;
		font-style: italic;
		color: #6b7280;
		margin-bottom: 0.5rem;
	}

	.practice-print-question {
		margin-bottom: 0.35rem;
		font-weight: 500;
		line-height: 1.6;
	}

	:global(.practice-print [data-print-role='answer-lines']) {
		border: 1.5px solid #ccc;
		border-radius: 2px;
		min-height: 60px;
		padding: 8px 12px 4px;
		margin-bottom: 1.25rem;
		background: repeating-linear-gradient(
			to bottom,
			transparent,
			transparent 27px,
			#ddd 27px,
			#ddd 28px
		);
	}

	.practice-print-hints {
		background: #f9fafb;
		padding: var(--rh-pad-card-tight);
		margin: 1rem 0;
		border-left: 3px solid #d1d5db;
	}

	.practice-print-hints-label {
		margin-bottom: 0.5rem;
	}

	.practice-print-hint {
		margin: 0.25rem 0;
		font-size: 0.875rem;
	}

	.practice-print-solution {
		border-top: 1px solid #d1d5db;
		padding-top: var(--rh-pad-card-tight);
		margin-top: 1rem;
	}

	.practice-print-answer {
		margin-top: 0.5rem;
	}
</style>
