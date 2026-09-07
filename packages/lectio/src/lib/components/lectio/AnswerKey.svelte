<script lang="ts">
	import type { AnswerKeyContent } from '$lib/schema/types';
	import { Card } from '$lib/components/ui/card';

	const DEFAULT_NOTE =
		'Tags show which misconception an answer is consistent with. They are indicative, not conclusive.';

	let { content }: { content: AnswerKeyContent } = $props();

	const label = $derived(content.label ?? 'Answer key');
	const note = $derived(content.note ?? DEFAULT_NOTE);
</script>

<Card class="border-0 bg-card shadow-none">
	<section
		class="answer-key"
		aria-label={label}
		data-lectio-block="answer-key"
		data-print-container="itemized"
	>
		<header class="answer-key-header">
			<h2 class="answer-key-label">{label}</h2>
			{#if note}
				<p class="answer-key-note">{note}</p>
			{/if}
		</header>

		<div class="answer-key-body">
			{#if content.entries.length === 0}
				<p class="answer-key-empty">No questions in this pack.</p>
			{:else}
				<ol class="answer-key-entries">
					{#each content.entries as entry}
						<li class="answer-key-entry" value={entry.question_number}>
							<p class="answer-key-question">{entry.question}</p>

							<div class="answer-key-response-group">
								<p class="answer-key-correct">
									<strong>Correct</strong>
									{#if entry.correct_key}
										<span>({entry.correct_key})</span>
									{/if}
									<span>{entry.correct_answer}</span>
								</p>

								{#if entry.diagnostics?.length}
									<div class="answer-key-diagnostics">
										{#each entry.diagnostics as diagnostic}
											<p
												class="answer-key-diagnostic"
												aria-label={`chose "${diagnostic.option_text}", consistent with: ${
													diagnostic.misconception_label || diagnostic.misconception_id
												}`}
											>
												chose "{diagnostic.option_text}"
												<span class="answer-key-arrow" aria-hidden="true">→</span>
												consistent with:
												{diagnostic.misconception_label || diagnostic.misconception_id}
											</p>
										{/each}
									</div>
								{/if}
							</div>
						</li>
					{/each}
				</ol>
			{/if}
		</div>
	</section>
</Card>

<style>
	.answer-key {
		box-sizing: border-box;
		width: 100%;
		padding: var(--rh-pad-card);
		color: var(--foreground);
	}

	.answer-key-header {
		margin-bottom: 1.5rem;
	}

	.answer-key-label {
		margin: 0;
		color: var(--foreground);
		font-size: 1.125rem;
		font-weight: 500;
		line-height: 1.4;
	}

	.answer-key-note,
	.answer-key-empty {
		margin: 0.35rem 0 0;
		color: var(--muted-foreground);
		font-size: 0.8125rem;
		font-weight: 400;
		line-height: 1.5;
	}

	.answer-key-entries {
		margin: 0;
		padding-left: 2rem;
	}

	.answer-key-entry {
		padding-left: 0.5rem;
		color: var(--foreground);
		font-size: 0.9375rem;
		line-height: 1.55;
		overflow-wrap: anywhere;
		break-inside: avoid;
		orphans: 2;
		widows: 2;
	}

	.answer-key-entry::marker {
		font-variant-numeric: tabular-nums;
		font-weight: 500;
	}

	.answer-key-entry + .answer-key-entry {
		margin-top: 1.5rem;
		padding-top: 1.5rem;
		border-top: 0.5px solid var(--border);
	}

	.answer-key-question,
	.answer-key-correct,
	.answer-key-diagnostic {
		margin: 0;
	}

	.answer-key-correct {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		margin-top: 0.75rem;
		color: var(--foreground);
	}

	.answer-key-response-group {
		break-inside: avoid;
	}

	.answer-key-diagnostics {
		display: grid;
		gap: 0.45rem;
		margin-top: 0.75rem;
		margin-left: 1.5rem;
		color: var(--muted-foreground);
		font-size: 0.875rem;
		font-weight: 400;
	}

	.answer-key-diagnostic {
		padding-left: 0.9rem;
		text-indent: -0.9rem;
		break-inside: avoid;
	}

	.answer-key-arrow {
		display: inline-block;
		margin-inline: 0.25rem;
	}

	@media print {
		.answer-key {
			break-before: page;
			display: table;
			padding: 0;
		}

		.answer-key-header {
			display: table-header-group;
		}

		.answer-key-body {
			display: table-row-group;
		}

		.answer-key-entry + .answer-key-entry {
			border-top-width: 0.5pt;
		}

		.answer-key-entry,
		.answer-key-diagnostic,
		.answer-key-response-group {
			break-inside: avoid;
		}
	}
</style>
