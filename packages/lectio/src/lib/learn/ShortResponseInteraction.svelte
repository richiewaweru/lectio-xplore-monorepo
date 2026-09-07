/**
 * Short-response shell: text input evaluated via numeric tolerance OR exact string
 * through the numeric path when numeric; otherwise treats as fill-blank single field.
 */
<script lang="ts">
	import type { FeedbackSpec } from '$lib/learn/interaction-contract';

	interface Props {
		prompt: string;
		acceptedAnswers: string[];
		feedback: FeedbackSpec;
		ariaLabel?: string;
	}

	let { prompt, acceptedAnswers, feedback, ariaLabel = prompt }: Props = $props();

	let raw = $state('');
	let submitted = $state(false);

	const multiResult = $derived.by(() => {
		if (!submitted) return null;
		const ok = acceptedAnswers.some(
			(a) => a.trim().toLowerCase() === raw.trim().toLowerCase()
		);
		return {
			outcome: ok ? ('correct' as const) : ('incorrect' as const),
			score_earned: ok ? 1 : 0,
			score_possible: 1,
			feedback: ok ? feedback.correct : feedback.incorrect
		};
	});
</script>

<div class="short-root" aria-label={ariaLabel} data-testid="short-response-interaction">
	<p class="prompt">{prompt}</p>
	<label>
		<span class="sr">Answer</span>
		<input
			type="text"
			bind:value={raw}
			disabled={submitted}
			aria-label="Answer"
			onkeydown={(e) => {
				if (e.key === 'Enter' && raw.trim() && !submitted) {
					e.preventDefault();
					submitted = true;
				}
			}}
		/>
	</label>
	<button
		type="button"
		class="submit"
		disabled={submitted || !raw.trim()}
		onclick={() => (submitted = true)}
	>
		Check
	</button>
	{#if multiResult}
		<p class="feedback" data-outcome={multiResult.outcome} role="status">{multiResult.feedback}</p>
	{/if}
</div>

<style>
	.short-root {
		display: grid;
		gap: 12px;
		border: 1px solid var(--rule, #d6d3d1);
		border-radius: 12px;
		background: var(--surface, #fff);
		padding: 14px;
		color: var(--ink, #1c1917);
	}
	.prompt {
		margin: 0;
		font-weight: 600;
	}
	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
	}
	input {
		width: 100%;
		border: 1px solid var(--rule, #d6d3d1);
		border-radius: 8px;
		padding: 10px 12px;
		background: var(--paper, #fafaf9);
		color: inherit;
		font: inherit;
		box-sizing: border-box;
	}
	.submit {
		justify-self: start;
		border: 1px solid var(--accent, #0f766e);
		border-radius: 8px;
		background: var(--accent, #0f766e);
		color: white;
		padding: 8px 12px;
		font-weight: 600;
		cursor: pointer;
	}
	.feedback {
		margin: 0;
		font-size: 14px;
	}
</style>
