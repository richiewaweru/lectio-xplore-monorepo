<script lang="ts">
	import { evaluateSequence, type FeedbackSpec } from '$lib/learn/interaction-contract';

	interface Step {
		id: string;
		label: string;
	}

	export type ServerEvaluation = {
		outcome: string;
		feedback: string;
		score_earned?: number;
		score_possible?: number;
	};

	interface Props {
		prompt: string;
		steps: Step[];
		correctOrder: string[];
		feedback: FeedbackSpec;
		ariaLabel?: string;
		/** Restored order from a persisted attempt. */
		initialOrder?: string[];
		/** When set, UI shows authoritative feedback (server or prior attempt). */
		initialEvaluation?: ServerEvaluation | null;
		/**
		 * Production bridge: persist via caller. Return value is authoritative —
		 * local evaluateSequence is only used when this is omitted (preview).
		 */
		onSubmit?: (order: string[]) => Promise<ServerEvaluation>;
		disabled?: boolean;
	}

	let {
		prompt,
		steps,
		correctOrder,
		feedback,
		ariaLabel = prompt,
		initialOrder = undefined,
		initialEvaluation = null,
		onSubmit = undefined,
		disabled = false
	}: Props = $props();

	let order = $state<string[]>([]);
	let submitted = $state(false);
	let serverResult = $state<ServerEvaluation | null>(null);
	let submitting = $state(false);
	let error = $state<string | null>(null);

	$effect(() => {
		if (order.length === 0 && steps.length > 0) {
			order = initialOrder && initialOrder.length === steps.length
				? [...initialOrder]
				: steps.map((s) => s.id);
		}
	});

	$effect(() => {
		if (initialEvaluation) {
			submitted = true;
			serverResult = initialEvaluation;
		}
	});

	const localResult = $derived(
		submitted && !onSubmit && !serverResult
			? evaluateSequence({ order: correctOrder }, { order }, feedback)
			: null
	);

	const display = $derived(
		serverResult
			? { outcome: serverResult.outcome, feedback: serverResult.feedback }
			: localResult
				? { outcome: localResult.outcome, feedback: localResult.feedback }
				: null
	);

	function move(index: number, dir: -1 | 1) {
		if (submitted || disabled || submitting) return;
		const next = index + dir;
		if (next < 0 || next >= order.length) return;
		const copy = [...order];
		[copy[index], copy[next]] = [copy[next], copy[index]];
		order = copy;
	}

	function labelFor(id: string) {
		return steps.find((s) => s.id === id)?.label ?? id;
	}

	async function handleCheck() {
		if (submitted || disabled || submitting) return;
		error = null;
		if (onSubmit) {
			submitting = true;
			try {
				const result = await onSubmit(order);
				serverResult = result;
				submitted = true;
			} catch (err) {
				error = err instanceof Error ? err.message : 'Submit failed';
			} finally {
				submitting = false;
			}
			return;
		}
		submitted = true;
	}
</script>

<div class="seq-root" aria-label={ariaLabel} data-testid="sequence-interaction">
	<p class="prompt">{prompt}</p>
	<ol class="steps">
		{#each order as id, index (id)}
			<li>
				<span class="label">{labelFor(id)}</span>
				<div class="moves">
					<button
						type="button"
						aria-label={`Move ${labelFor(id)} up`}
						disabled={submitted || disabled || submitting || index === 0}
						onclick={() => move(index, -1)}
					>
						↑
					</button>
					<button
						type="button"
						aria-label={`Move ${labelFor(id)} down`}
						disabled={submitted || disabled || submitting || index === order.length - 1}
						onclick={() => move(index, 1)}
					>
						↓
					</button>
				</div>
			</li>
		{/each}
	</ol>
	<button
		type="button"
		class="submit"
		disabled={submitted || disabled || submitting}
		onclick={handleCheck}
		data-testid="sequence-check"
	>
		{submitting ? 'Saving…' : 'Check'}
	</button>
	{#if error}
		<p class="error" role="alert">{error}</p>
	{/if}
	{#if display}
		<p class="feedback" data-outcome={display.outcome} role="status">{display.feedback}</p>
	{/if}
</div>

<style>
	.seq-root {
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
	.steps {
		margin: 0;
		padding: 0;
		list-style: none;
		display: grid;
		gap: 8px;
	}
	.steps li {
		display: flex;
		justify-content: space-between;
		gap: 10px;
		align-items: center;
		border: 1px solid var(--rule, #d6d3d1);
		border-radius: 10px;
		background: var(--paper, #fafaf9);
		padding: 8px 10px;
	}
	.moves {
		display: flex;
		gap: 4px;
	}
	.moves button {
		border: 1px solid var(--rule, #d6d3d1);
		border-radius: 6px;
		background: white;
		width: 28px;
		height: 28px;
		cursor: pointer;
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
	.error {
		margin: 0;
		font-size: 13px;
		color: var(--amber, #b45309);
	}
</style>
