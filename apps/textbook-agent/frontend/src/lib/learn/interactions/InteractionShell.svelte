<script lang="ts">
	/**
	 * Mountable wrappers for the eight retained Learn interactions.
	 * Preview: local eval. Production: onSubmit → runtime API (attempts outside content).
	 */
	import type { InteractionNode, InteractionType } from '$lib/learn/document/types';
	import { normalizeFeedback } from './feedback';
	import {
		evalChoice,
		evalFillBlank,
		evalMultiSelect,
		evalNumeric,
		evalPairs,
		evalSequence,
		evalShortResponse,
		savePrediction
	} from './local-eval';
	import type { InteractionSubmitHandler, ServerEvaluation } from './types';
	import InlineMarkup from '$lib/learn/document/renderers/InlineMarkup.svelte';

	interface Props {
		node: InteractionNode;
		onSubmit?: InteractionSubmitHandler;
		initialEvaluation?: ServerEvaluation | null;
		disabled?: boolean;
		questionNumber?: number;
	}

	let {
		node,
		onSubmit = undefined,
		initialEvaluation = null,
		disabled = false,
		questionNumber = undefined
	}: Props = $props();

	const prompt = $derived(node.display_prompt?.trim() || node.prompt?.trim() || 'Question');
	const role = $derived(node.role ?? (node.assessment_mode === 'practice' ? 'practice' : 'check'));
	const submitLabel = $derived(role === 'predict' ? 'Lock in my prediction' : 'Check my answer');
	const config = $derived((node.config ?? {}) as Record<string, unknown>);
	const feedback = $derived(normalizeFeedback(node.feedback, role));
	const type = $derived(node.interaction_type as InteractionType);
	const modeLabel = $derived(
		role === 'predict' ? 'Prediction — not marked' : role === 'practice' ? 'Practice' : type === 'choice' ? 'Check — choose one' : 'Check'
	);

	let submitted = $state(false);
	let submitting = $state(false);
	let error = $state<string | null>(null);
	let serverResult = $state<ServerEvaluation | null>(null);

	// choice / multi
	let selectedOne = $state<string | null>(null);
	let selectedMany = $state<string[]>([]);
	// fill / short / numeric
	let blanks = $state<string[]>([]);
	let textAnswer = $state('');
	let numericRaw = $state('');
	// pairs / classify
	let selectedLeft = $state<string | null>(null);
	let matches = $state<Array<{ left: string; right: string }>>([]);
	// sequence
	let order = $state<string[]>([]);

	$effect(() => {
		if (initialEvaluation) {
			submitted = true;
			serverResult = role === 'predict' ? savePrediction(feedback) : initialEvaluation;
		}
	});

	$effect(() => {
		const cfg = config;
		const t = type;
		if (t === 'fill-blank') {
			const answers = Array.isArray(cfg.answers) ? cfg.answers : [];
			const ids = Array.isArray(cfg.blank_ids) ? cfg.blank_ids : [];
			const n = Math.max(answers.length, ids.length, 1);
			if (blanks.length !== n) blanks = Array.from({ length: n }, (_, i) => blanks[i] ?? '');
		}
		if (t === 'sequence' && order.length === 0) {
			const items = sequenceItems(cfg);
			order = items.map((s) => s.id);
		}
	});

	const choiceOptions = $derived(
		Array.isArray(config.options)
			? (config.options as Array<{ id: string; text?: string; label?: string }>).map((o, index) => ({
					id: String(o.id),
					text: String(o.text ?? o.label ?? o.id),
					letter: String.fromCharCode(65 + index)
				}))
			: []
	);

	const correctOptionId = $derived(String(config.correct_option_id ?? ''));
	const correctOptionIds = $derived(
		Array.isArray(config.correct_option_ids)
			? config.correct_option_ids.map(String)
			: []
	);

	const fillAnswers = $derived(
		Array.isArray(config.answers) ? config.answers.map(String) : []
	);
	const fillCaseSensitive = $derived(Boolean(config.case_sensitive));

	const numericExpected = $derived(Number(config.value ?? 0));
	const numericTolerance = $derived(Number(config.tolerance ?? 0));

	const shortAccepted = $derived(
		Array.isArray(config.answers)
			? config.answers.map(String)
			: Array.isArray(config.accepted_answers)
				? config.accepted_answers.map(String)
				: []
	);

	const pairList = $derived(
		Array.isArray(config.pairs)
			? (config.pairs as Array<{ left: string; right: string }>).map((p) => ({
					left: String(p.left),
					right: String(p.right)
				}))
			: []
	);

	const matchLeft = $derived(
		pairList.map((p) => ({ id: p.left, label: p.left }))
	);
	const matchRight = $derived(
		[...new Set(pairList.map((p) => p.right))].map((id) => ({ id, label: id }))
	);

	const classifyCategories = $derived(
		Array.isArray(config.categories)
			? (config.categories as Array<{ id: string; label?: string }>).map((c) => ({
					id: String(c.id),
					label: String(c.label ?? c.id)
				}))
			: [...new Set(pairList.map((p) => p.right))].map((id) => ({ id, label: id }))
	);
	const classifyItems = $derived(
		Array.isArray(config.items)
			? (config.items as Array<{ id: string; label?: string }>).map((i) => ({
					id: String(i.id),
					label: String(i.label ?? i.id)
				}))
			: pairList.map((p) => ({ id: p.left, label: p.left }))
	);

	const sequenceSteps = $derived(sequenceItems(config));
	const correctOrder = $derived(
		Array.isArray(config.order) ? config.order.map(String) : sequenceSteps.map((s) => s.id)
	);

	const display = $derived.by((): ServerEvaluation | null => {
		if (serverResult) return serverResult;
		if (!submitted || onSubmit) return null;
		if (role === 'predict') return savePrediction(feedback);
		switch (type) {
			case 'choice':
				return selectedOne
					? evalChoice(correctOptionId, selectedOne, feedback)
					: null;
			case 'multi-select':
				return evalMultiSelect(correctOptionIds, selectedMany, feedback);
			case 'fill-blank':
				return evalFillBlank(fillAnswers, blanks, feedback, fillCaseSensitive);
			case 'numeric': {
				const parsed = Number(numericRaw);
				return evalNumeric(numericExpected, numericTolerance, parsed, feedback);
			}
			case 'short-response':
				return evalShortResponse(shortAccepted, textAnswer, feedback);
			case 'match-pairs':
			case 'classify':
				return evalPairs(pairList, matches, feedback);
			case 'sequence':
				return evalSequence(correctOrder, order, feedback);
			default:
				return null;
		}
	});

	function sequenceItems(cfg: Record<string, unknown>) {
		if (Array.isArray(cfg.items)) {
			return (cfg.items as Array<{ id: string; label?: string }>).map((i) => ({
				id: String(i.id),
				label: String(i.label ?? i.id)
			}));
		}
		if (Array.isArray(cfg.order)) {
			return cfg.order.map((id) => ({ id: String(id), label: String(id) }));
		}
		return [];
	}

	function buildResponse(): Record<string, unknown> {
		switch (type) {
			case 'choice':
				return { selected_option_id: selectedOne };
			case 'multi-select':
				return { selected_option_ids: selectedMany };
			case 'fill-blank':
				return { blanks };
			case 'numeric':
				return { value: Number(numericRaw) };
			case 'short-response':
				return { text: textAnswer };
			case 'match-pairs':
			case 'classify':
				return { matches };
			case 'sequence':
				return { order };
			default:
				return {};
		}
	}

	async function handleCheck() {
		if (submitted || disabled || submitting) return;
		error = null;
		if (onSubmit) {
			submitting = true;
			try {
				const result = await onSubmit(buildResponse());
				serverResult = role === 'predict' ? savePrediction(feedback) : result;
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

	function canSubmit(): boolean {
		if (disabled || submitted || submitting) return false;
		switch (type) {
			case 'choice':
				return selectedOne != null;
			case 'multi-select':
				return selectedMany.length > 0;
			case 'fill-blank':
				return blanks.every((b) => b.trim().length > 0);
			case 'numeric':
				return numericRaw.trim().length > 0;
			case 'short-response':
				return textAnswer.trim().length > 0;
			case 'match-pairs':
			case 'classify':
				return matches.length > 0;
			case 'sequence':
				return order.length > 0;
			default:
				return false;
		}
	}

	function toggleMulti(id: string) {
		if (submitted) return;
		selectedMany = selectedMany.includes(id)
			? selectedMany.filter((x) => x !== id)
			: [...selectedMany, id];
	}

	function pickLeft(id: string) {
		if (submitted) return;
		selectedLeft = id;
	}

	function pickRight(id: string) {
		if (submitted || !selectedLeft) return;
		matches = [
			...matches.filter((m) => m.left !== selectedLeft && m.right !== id),
			{ left: selectedLeft, right: id }
		];
		selectedLeft = null;
	}

	function pickClassifyCategory(id: string) {
		if (submitted || !selectedLeft) return;
		matches = [
			...matches.filter((m) => m.left !== selectedLeft),
			{ left: selectedLeft, right: id }
		];
		selectedLeft = null;
	}

	function moveSeq(index: number, dir: -1 | 1) {
		if (submitted || submitting) return;
		const next = index + dir;
		if (next < 0 || next >= order.length) return;
		const copy = [...order];
		[copy[index], copy[next]] = [copy[next]!, copy[index]!];
		order = copy;
	}

	function labelFor(id: string) {
		return sequenceSteps.find((s) => s.id === id)?.label ?? id;
	}
</script>

<section
	class="ix-shell"
	data-testid="interaction-shell"
>
	<header class="task-header">
		<strong>YOUR TURN · QUESTION {questionNumber ?? ''}</strong>
		<span>{modeLabel}</span>
	</header>
	<div class="task-body">
		<p class="prompt"><InlineMarkup value={prompt} /></p>

	{#if type === 'choice'}
		<ul class="options" role="group" aria-label="Choose one">
			{#each choiceOptions as option (option.id)}
				<li>
					<button
						type="button"
						class="option"
						class:selected={selectedOne === option.id}
						aria-pressed={selectedOne === option.id}
						disabled={submitted || disabled}
						onclick={() => (selectedOne = option.id)}
					>
						<span class="option-letter" aria-hidden="true">{option.letter}</span>
						<span><InlineMarkup value={option.text} /></span>
					</button>
				</li>
			{/each}
		</ul>
	{:else if type === 'multi-select'}
		<ul class="options" role="group" aria-label={prompt}>
			{#each choiceOptions as option (option.id)}
				<li>
					<button
						type="button"
						class="option"
						class:selected={selectedMany.includes(option.id)}
						aria-pressed={selectedMany.includes(option.id)}
						disabled={submitted || disabled}
						onclick={() => toggleMulti(option.id)}
					>
						<span class="option-letter" aria-hidden="true">{option.letter}</span>
						<span><InlineMarkup value={option.text} /></span>
					</button>
				</li>
			{/each}
		</ul>
	{:else if type === 'fill-blank'}
		<div class="blanks" data-testid="fill-blank-interaction">
			{#each blanks as _, i (i)}
				<label class="field">
					<span class="sr">Blank {i + 1}</span>
					<input
						type="text"
						aria-label={`Blank ${i + 1}`}
						value={blanks[i]}
						disabled={submitted || disabled}
						oninput={(e) => {
							const next = [...blanks];
							next[i] = (e.currentTarget as HTMLInputElement).value;
							blanks = next;
						}}
					/>
				</label>
			{/each}
		</div>
	{:else if type === 'numeric'}
		<label class="field">
			<span class="sr">Answer</span>
			<input
				type="number"
				aria-label="Answer"
				value={numericRaw}
				disabled={submitted || disabled}
				oninput={(e) => (numericRaw = (e.currentTarget as HTMLInputElement).value)}
			/>
		</label>
	{:else if type === 'short-response'}
		<label class="field">
			<span class="sr">Answer</span>
			<input
				type="text"
				aria-label="Answer"
				bind:value={textAnswer}
				disabled={submitted || disabled}
			/>
		</label>
	{:else if type === 'match-pairs'}
		<div class="columns">
			<ul class="col">
				{#each matchLeft as item (item.id)}
					<li>
						<button
							type="button"
							class="option"
							class:selected={selectedLeft === item.id}
							class:matched={matches.some((m) => m.left === item.id)}
							aria-pressed={selectedLeft === item.id || matches.some((m) => m.left === item.id)}
							disabled={submitted || disabled}
							onclick={() => pickLeft(item.id)}
						>
							<InlineMarkup value={item.label} />
						</button>
					</li>
				{/each}
			</ul>
			<ul class="col">
				{#each matchRight as item (item.id)}
					<li>
						<button
							type="button"
							class="option"
							class:matched={matches.some((m) => m.right === item.id)}
							aria-pressed={matches.some((m) => m.right === item.id)}
							disabled={submitted || disabled || !selectedLeft}
							onclick={() => pickRight(item.id)}
						>
							<InlineMarkup value={item.label} />
						</button>
					</li>
				{/each}
			</ul>
		</div>
	{:else if type === 'classify'}
		<ul class="chips">
			{#each classifyItems as item (item.id)}
				<li>
					<button
						type="button"
						class="chip"
						class:selected={selectedLeft === item.id}
						class:matched={matches.some((m) => m.left === item.id)}
						disabled={submitted || disabled}
						onclick={() => pickLeft(item.id)}
					>
						<InlineMarkup value={item.label} />
					</button>
				</li>
			{/each}
		</ul>
		<ul class="chips">
			{#each classifyCategories as cat (cat.id)}
				<li>
					<button
						type="button"
						class="chip"
						disabled={submitted || disabled || !selectedLeft}
						onclick={() => pickClassifyCategory(cat.id)}
					>
						<InlineMarkup value={cat.label} />
					</button>
				</li>
			{/each}
		</ul>
	{:else if type === 'sequence'}
		<ol class="steps">
			{#each order as id, index (id)}
				<li>
					<span><InlineMarkup value={labelFor(id)} /></span>
					<div class="moves">
						<button
							type="button"
							aria-label={`Move ${labelFor(id)} up`}
							disabled={submitted || disabled || submitting || index === 0}
							onclick={() => moveSeq(index, -1)}
						>
							↑
						</button>
						<button
							type="button"
							aria-label={`Move ${labelFor(id)} down`}
							disabled={submitted || disabled || submitting || index === order.length - 1}
							onclick={() => moveSeq(index, 1)}
						>
							↓
						</button>
					</div>
				</li>
			{/each}
		</ol>
	{/if}

		<button
			type="button"
			class="submit"
			disabled={!canSubmit()}
			onclick={handleCheck}
			data-testid="interaction-check"
		>
			{submitting ? 'Saving…' : submitLabel}
		</button>

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
	.options,
	.steps,
	.chips,
	.col {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 8px;
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.columns {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}
	.option,
	.chip {
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
	.option-letter { display: grid; place-items: center; flex: 0 0 28px; width: 28px; height: 28px; border-radius: 50%; background: var(--sand, #f3eee3); font-weight: 700; }
	.chip {
		width: auto;
		border-radius: 999px;
	}
	.option.selected,
	.option.matched,
	.chip.selected,
	.chip.matched {
		border-color: var(--green, #1b5e40);
		background: var(--sand, #f3eee3);
	}
	.field {
		display: grid;
		gap: 6px;
	}
	.blanks {
		display: grid;
		gap: 8px;
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
		box-sizing: border-box;
		border: 1px solid var(--rule, #d6d3d1);
		border-radius: 8px;
		padding: 10px 12px;
		background: var(--paper, #fafaf9);
		color: inherit;
		font: inherit;
	}
	.steps li {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 10px;
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
