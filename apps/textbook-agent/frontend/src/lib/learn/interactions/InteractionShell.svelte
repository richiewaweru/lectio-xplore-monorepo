<script lang="ts">
	/**
	 * The frame around one Learn question: header, prompt, a kind component, controls, feedback.
	 *
	 * State machine: editing --Check--> checked --Try again--> editing.
	 * Preview (no onSubmit): local eval mirrors the server's marking and retry rules.
	 * Production: onSubmit → runtime API, which owns attempts_left / reveal.
	 */
	import { untrack, type Component } from 'svelte';
	import type { InteractionNode, InteractionType } from '$lib/learn/document/types';
	import { roleOf } from './attempt-rules';
	import { normalizeFeedback } from './feedback';
	import { evaluateLocalAttempt, savePrediction } from './local-eval';
	import type {
		InteractionSubmitHandler,
		ItemResults,
		KindProgress,
		LearnerResponse,
		ServerEvaluation
	} from './types';
	import InlineMarkup from '$lib/learn/document/renderers/InlineMarkup.svelte';
	import ChoiceInteraction from './kinds/ChoiceInteraction.svelte';
	import ClassifyInteraction from './kinds/ClassifyInteraction.svelte';
	import FillBlankInteraction from './kinds/FillBlankInteraction.svelte';
	import MatchPairsInteraction from './kinds/MatchPairsInteraction.svelte';
	import MultiSelectInteraction from './kinds/MultiSelectInteraction.svelte';
	import NumericInteraction from './kinds/NumericInteraction.svelte';
	import SequenceInteraction from './kinds/SequenceInteraction.svelte';
	import ShortResponseInteraction from './kinds/ShortResponseInteraction.svelte';

	/** What the shell needs from a kind component (reached through bind:this). */
	interface KindHandle {
		load(saved: LearnerResponse | null | undefined): void;
		reset(): void;
		keepCorrect(results?: ItemResults): void;
	}

	const KINDS: Partial<Record<InteractionType, Component<any>>> = {
		choice: ChoiceInteraction,
		'multi-select': MultiSelectInteraction,
		numeric: NumericInteraction,
		'short-response': ShortResponseInteraction,
		'fill-blank': FillBlankInteraction,
		classify: ClassifyInteraction,
		'match-pairs': MatchPairsInteraction,
		sequence: SequenceInteraction
	};

	interface Props {
		node: InteractionNode;
		onSubmit?: InteractionSubmitHandler;
		/** Saved result to restore on resume. */
		initialEvaluation?: ServerEvaluation | null;
		/** Saved answer to restore on resume. */
		initialResponse?: LearnerResponse | null;
		disabled?: boolean;
		questionNumber?: number;
	}

	let {
		node,
		onSubmit = undefined,
		initialEvaluation = null,
		initialResponse = null,
		disabled = false,
		questionNumber = undefined
	}: Props = $props();

	const prompt = $derived(node.display_prompt?.trim() || node.prompt?.trim() || 'Question');
	const role = $derived(roleOf(node));
	const submitLabel = $derived(role === 'predict' ? 'Lock in my prediction' : 'Check my answer');
	const config = $derived((node.config ?? {}) as Record<string, unknown>);
	const feedback = $derived(normalizeFeedback(node.feedback, role));
	const type = $derived(node.interaction_type as InteractionType);
	const Kind = $derived(KINDS[type]);
	const modeLabel = $derived(
		role === 'predict'
			? 'Prediction — not marked'
			: role === 'practice'
				? 'Practice'
				: type === 'choice'
					? 'Check — choose one'
					: 'Check'
	);

	function lockedPrediction(): ServerEvaluation {
		return { ...savePrediction(feedback), attempts_used: 1, attempts_left: 0, reveal: null };
	}

	// Resume: restore the saved result once. Later prop changes (a refetch after submit) are ignored.
	const resumed = untrack(() =>
		initialEvaluation ? (role === 'predict' ? lockedPrediction() : initialEvaluation) : null
	);

	let phase = $state<'editing' | 'checked'>(resumed ? 'checked' : 'editing');
	let result = $state<ServerEvaluation | null>(resumed);
	let submitting = $state(false);
	let error = $state<string | null>(null);
	let showingAnswer = $state(false);
	let myResponse: LearnerResponse | null = null;
	/** Outcomes of earlier tries (preview only; the server counts for real learners). */
	let localOutcomes: string[] = [];

	let kind = $state<any>();
	let response = $state<LearnerResponse>({});
	let progress = $state<KindProgress>({ done: 0, total: 1 });

	const total = $derived(progress.total);
	const complete = $derived(progress.total > 0 && progress.done === progress.total);
	const canCheck = $derived(
		phase === 'editing' && !disabled && !submitting && !showingAnswer && complete
	);
	const showProgress = $derived(
		phase === 'editing' &&
			total > 1 &&
			!complete &&
			['match-pairs', 'classify', 'sequence', 'fill-blank'].includes(type)
	);
	const progressWord = $derived(type === 'fill-blank' ? 'filled' : 'placed');

	const outcome = $derived(result?.outcome);
	const attemptsLeft = $derived(result?.attempts_left ?? null);
	const canRetry = $derived(
		phase === 'checked' &&
			!disabled &&
			!!result &&
			role !== 'predict' &&
			outcome !== 'correct' &&
			outcome !== 'pending-review' &&
			(attemptsLeft === null || attemptsLeft > 0)
	);
	const reveal = $derived(phase === 'checked' ? (result?.reveal ?? null) : null);
	const triesNote = $derived.by(() => {
		if (!result || result.attempts_left == null || result.attempts_left <= 0) return '';
		if (outcome === 'correct' || outcome === 'pending-review') return '';
		const n = result.attempts_left;
		return `${n} ${n === 1 ? 'try' : 'tries'} left`;
	});
	const kindDisabled = $derived(disabled || phase === 'checked' || submitting);
	const marks = $derived(
		phase === 'checked' && !showingAnswer ? (result?.item_results ?? null) : null
	);
	const display = $derived(phase === 'checked' ? result : null);

	async function handleCheck() {
		if (!canCheck) return;
		error = null;
		const body = $state.snapshot(response) as LearnerResponse;
		if (onSubmit) {
			submitting = true;
			try {
				const evaluation = await onSubmit(body);
				result = role === 'predict' ? lockedPrediction() : evaluation;
				phase = 'checked';
			} catch (err) {
				error = err instanceof Error ? err.message : 'Submit failed';
			} finally {
				submitting = false;
			}
			return;
		}
		const evaluation = evaluateLocalAttempt(node, body, feedback, localOutcomes);
		localOutcomes = [...localOutcomes, evaluation.outcome];
		result = evaluation;
		phase = 'checked';
	}

	function handleClear() {
		if (phase !== 'editing') return;
		kind?.reset();
		error = null;
	}

	function leaveAnswerView() {
		if (!showingAnswer) return;
		showingAnswer = false;
		kind?.load(myResponse);
	}

	function handleTryAgain() {
		if (!canRetry) return;
		leaveAnswerView();
		kind?.keepCorrect(result?.item_results ?? undefined);
		phase = 'editing';
		error = null;
	}

	function toggleAnswer() {
		if (!reveal) return;
		if (showingAnswer) {
			leaveAnswerView();
			return;
		}
		myResponse = $state.snapshot(response) as LearnerResponse;
		kind?.load(reveal);
		showingAnswer = true;
	}
</script>

<section
	class="ix-shell"
	data-testid="interaction-shell"
	data-phase={phase}
>
	<header class="task-header">
		<strong>YOUR TURN · QUESTION {questionNumber ?? ''}</strong>
		<span>{modeLabel}</span>
	</header>
	<div class="task-body">
		<p class="prompt"><InlineMarkup value={prompt} /></p>

		{#if showingAnswer}
			<p class="answer-label" data-testid="correct-answer-label">Correct answer</p>
		{/if}

		{#if Kind}
			<Kind
				bind:this={kind}
				{config}
				disabled={kindDisabled}
				itemResults={marks}
				{initialResponse}
				bind:response
				bind:progress
			/>
		{/if}

		<div class="controls">
			{#if phase === 'editing'}
				<button
					type="button"
					class="submit"
					disabled={!canCheck}
					onclick={handleCheck}
					data-testid="interaction-check"
				>
					{submitting ? 'Saving…' : submitLabel}
				</button>
				<button
					type="button"
					class="secondary"
					disabled={disabled || submitting || progress.done === 0}
					onclick={handleClear}
					data-testid="interaction-clear"
				>
					Clear
				</button>
				{#if showProgress}
					<span class="note" data-testid="interaction-progress"
						>{progress.done} of {total} {progressWord}</span
					>
				{/if}
			{:else}
				{#if canRetry}
					<button
						type="button"
						class="submit"
						onclick={handleTryAgain}
						data-testid="interaction-try-again"
					>
						Try again
					</button>
				{/if}
				{#if reveal}
					<button
						type="button"
						class="secondary"
						onclick={toggleAnswer}
						data-testid="interaction-show-answer"
					>
						{showingAnswer ? 'Show my answer' : 'Show answer'}
					</button>
				{/if}
			{/if}
			{#if triesNote}<span class="note" data-testid="interaction-tries">{triesNote}</span>{/if}
		</div>

		{#if error}<p class="error" role="alert"><InlineMarkup value={error} /></p>{/if}
		{#if display}<p class="feedback" data-outcome={display.outcome} role="status">{#if display.outcome === 'correct'}<svg class="feedback-icon" data-testid="feedback-correct-icon" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="11" fill="#1B5E40" /><path d="M7 12.5l3.2 3.2L17 8.8" fill="none" stroke="#E4F0E8" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" /></svg>{/if}<span class="feedback-text"><InlineMarkup value={display.feedback} /></span></p>{/if}
	</div>
</section>

<style>
	.ix-shell {
		display: grid;
		gap: 0;
		border: 2px solid var(--ink, #1c2321);
		border-radius: 14px;
		background: var(--surface, #fff);
		overflow: hidden;
		color: var(--ink, #1c1917);
	}
	.task-header { display: flex; justify-content: space-between; gap: 12px; padding: 13px 18px; background: var(--ink, #1c2321); color: var(--surface, #fff); font-size: 14px; letter-spacing: .06em; text-transform: uppercase; }
	.task-header span { color: var(--sand, #f3eee3); font-weight: 400; }
	.task-body { display: grid; gap: 16px; padding: 22px; }
	.prompt {
		margin: 0;
		font-size: 20px;
		font-weight: 700;
		line-height: 1.4;
	}
	.answer-label {
		margin: 0;
		font-size: 13px;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--green, #1b5e40);
	}

	/* Kind components render inside the frame; their markup is styled here. */
	.ix-shell :global(.options),
	.ix-shell :global(.steps),
	.ix-shell :global(.chips),
	.ix-shell :global(.col) {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 8px;
	}
	.ix-shell :global(.chips) {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.ix-shell :global(.columns) {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}
	.ix-shell :global(.option),
	.ix-shell :global(.chip) {
		width: 100%;
		text-align: left;
		min-height: 56px;
		display: flex;
		align-items: center;
		gap: 12px;
		border: 1px solid var(--rule-strong, #c9c3b5);
		border-radius: 10px;
		background: var(--surface, #fff);
		padding: 12px 14px;
		cursor: pointer;
		color: inherit;
		font: inherit;
	}
	.ix-shell :global(.option:disabled),
	.ix-shell :global(.chip:disabled) {
		cursor: default;
	}
	.ix-shell :global(.option-letter) { display: grid; place-items: center; flex: 0 0 28px; width: 28px; height: 28px; border-radius: 50%; background: var(--sand, #f3eee3); font-weight: 700; }
	.ix-shell :global(.chip) {
		width: auto;
		border-radius: 999px;
	}
	.ix-shell :global(.option.selected),
	.ix-shell :global(.option.matched),
	.ix-shell :global(.chip.selected),
	.ix-shell :global(.chip.matched) {
		border-color: var(--green, #1b5e40);
		background: var(--sand, #f3eee3);
	}
	.ix-shell :global(.placed-note) {
		margin-left: auto;
		font-size: 13px;
		opacity: 0.75;
	}
	/* Marks after a check */
	.ix-shell :global([data-mark='right']) {
		border-color: #1b5e40;
		background: var(--green-tint, #e4f0e8);
	}
	.ix-shell :global([data-mark='wrong']) {
		border-color: #b3261e;
		background: #fbeceb;
	}
	.ix-shell :global([data-mark='missed']) {
		border-style: dashed;
		border-color: #b3261e;
	}
	.ix-shell :global(.field) {
		display: grid;
		gap: 6px;
	}
	.ix-shell :global(.blanks) {
		display: grid;
		gap: 8px;
	}
	.ix-shell :global(.sr) {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
	}
	.ix-shell :global(input) {
		width: 100%;
		box-sizing: border-box;
		border: 1px solid var(--rule, #d6d3d1);
		border-radius: 8px;
		padding: 10px 12px;
		background: var(--paper, #fafaf9);
		color: inherit;
		font: inherit;
	}
	.ix-shell :global(.steps li) {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 10px;
		border: 1px solid var(--rule, #d6d3d1);
		border-radius: 10px;
		background: var(--paper, #fafaf9);
		padding: 8px 10px;
	}
	.ix-shell :global(.moves) {
		display: flex;
		gap: 4px;
	}
	.ix-shell :global(.moves button) {
		border: 1px solid var(--rule, #d6d3d1);
		border-radius: 6px;
		background: white;
		width: 28px;
		height: 28px;
		cursor: pointer;
	}

	.controls {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px;
	}
	.submit {
		min-height: 48px;
		border: 1px solid var(--action, #c2410c);
		border-radius: 8px;
		background: var(--action, #c2410c);
		color: white;
		padding: 10px 16px;
		font-weight: 600;
		cursor: pointer;
	}
	.submit:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.secondary {
		min-height: 48px;
		border: 1px solid var(--rule-strong, #c9c3b5);
		border-radius: 8px;
		background: transparent;
		color: inherit;
		padding: 10px 14px;
		font: inherit;
		cursor: pointer;
	}
	.secondary:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}
	.note {
		font-size: 14px;
		opacity: 0.75;
	}
	.feedback {
		margin: 0;
		padding: 12px 14px;
		border-radius: 8px;
		background: var(--green-tint, #e4f0e8);
		font-size: 16px;
		line-height: 1.5;
		display: flex;
		align-items: flex-start;
		gap: 10px;
	}
	.feedback-icon { flex: 0 0 22px; margin-top: 1px; color: #1b5e40; }
	.feedback-text { min-width: 0; }
	.error {
		margin: 0;
		font-size: 13px;
		color: var(--action, #c2410c);
	}
	@media (max-width: 520px) {
		.task-header { align-items: flex-start; flex-direction: column; gap: 3px; }
		.task-body { padding: 18px; }
		.prompt { font-size: 18px; }
	}
</style>
