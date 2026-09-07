<script lang="ts">
	import { evaluateNumeric, type FeedbackSpec } from '$lib/learn/interaction-contract';

	interface Props {
		prompt: string;
		value: number;
		tolerance?: number;
		feedback: FeedbackSpec;
		ariaLabel?: string;
		inputMode?: 'numeric' | 'text';
	}

	let {
		prompt,
		value,
		tolerance = 0,
		feedback,
		ariaLabel = prompt,
		inputMode = 'numeric'
	}: Props = $props();

	let raw = $state<string>('');
	let submitted = $state(false);

	const parsed = $derived(Number(raw));
	const result = $derived(
		submitted && Number.isFinite(parsed)
			? evaluateNumeric({ value, tolerance }, { value: parsed }, feedback)
			: submitted
				? {
						outcome: 'incorrect' as const,
						score_earned: 0,
						score_possible: 1,
						feedback: feedback.incorrect
					}
				: null
	);
</script>

<div class="num-root" aria-label={ariaLabel} data-testid="numeric-interaction">
	<p class="prompt">{prompt}</p>
	<label class="field">
		<span class="sr">Answer</span>
		<input
			type={inputMode === 'numeric' ? 'number' : 'text'}
			value={raw}
			disabled={submitted}
			aria-label="Answer"
			oninput={(e) => {
				raw = String((e.currentTarget as HTMLInputElement).value ?? '');
			}}
		/>
	</label>
	<button
		type="button"
		class="submit"
		disabled={submitted || String(raw).trim() === ''}
		onclick={() => (submitted = true)}
	>
		Check
	</button>
	{#if result}
		<p class="feedback" data-outcome={result.outcome} role="status">{result.feedback}</p>
	{/if}
</div>

<style>
	.num-root {
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
	.field {
		display: grid;
		gap: 6px;
	}
	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
	}
	input {
		border: 1px solid var(--rule, #d6d3d1);
		border-radius: 8px;
		padding: 10px 12px;
		background: var(--paper, #fafaf9);
		color: inherit;
		font: inherit;
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
