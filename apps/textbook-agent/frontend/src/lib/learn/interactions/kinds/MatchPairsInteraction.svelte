<script lang="ts">
	import { untrack } from 'svelte';
	import InlineMarkup from '$lib/learn/document/renderers/InlineMarkup.svelte';
	import type { ItemResults, KindProgress, LearnerResponse } from '../types';
	import MarkBadge from './MarkBadge.svelte';
	import { pointerDrag, targetAt } from './drag';
	import { mapResults } from './shared';

	interface Props {
		config: Record<string, unknown>;
		disabled?: boolean;
		itemResults?: ItemResults | undefined;
		initialResponse?: LearnerResponse | null;
		response?: LearnerResponse;
		progress?: KindProgress;
	}

	let {
		config,
		disabled = false,
		itemResults = null,
		initialResponse = null,
		response = $bindable({}),
		progress = $bindable({ done: 0, total: 1 })
	}: Props = $props();

	type Match = { left: string; right: string };

	const pairList = $derived(
		Array.isArray(config.pairs)
			? (config.pairs as Array<{ left: string; right: string }>).map((p) => ({
					left: String(p.left),
					right: String(p.right)
				}))
			: []
	);
	const left = $derived(
		Array.isArray(config.left_items)
			? (config.left_items as unknown[]).map((v) => ({ id: String(v), label: String(v) }))
			: pairList.map((p) => ({ id: p.left, label: p.left }))
	);
	const right = $derived(
		Array.isArray(config.right_items)
			? (config.right_items as unknown[]).map((v) => ({ id: String(v), label: String(v) }))
			: [...new Set(pairList.map((p) => p.right))].map((id) => ({ id, label: id }))
	);

	const uid = $props.id();
	let selectedLeft = $state<string | null>(null);
	let hoverRight = $state<string | null>(null);
	let announcement = $state('');
	let matches = $state<Match[]>([]);
	const marks = $derived(mapResults(itemResults));

	export function load(saved: LearnerResponse | null | undefined) {
		const m = saved?.matches;
		matches = Array.isArray(m)
			? (m as Array<{ left: unknown; right: unknown }>).map((x) => ({
					left: String(x.left),
					right: String(x.right)
				}))
			: [];
		selectedLeft = null;
	}
	export function reset() {
		matches = [];
		selectedLeft = null;
	}
	/** Keep the placements that were right; return the wrong ones. */
	export function keepCorrect(results?: ItemResults) {
		const map = mapResults(results);
		matches = map ? matches.filter((m) => map[m.left] === true) : [];
		selectedLeft = null;
	}

	untrack(() => load(initialResponse));

	const matchOfLeft = (id: string) => matches.find((m) => m.left === id);
	const matchOfRight = (id: string) => matches.find((m) => m.right === id);
	const labelOf = (id: string) => right.find((r) => r.id === id)?.label ?? id;
	const letterOf = (id: string) => String.fromCharCode(65 + Math.max(0, right.findIndex((r) => r.id === id)));
	const numberOf = (id: string) => left.findIndex((l) => l.id === id) + 1;
	const plain = (s: string) => s.replace(/[*_~^`]/g, '');

	function markFor(leftId: string | undefined): 'right' | 'wrong' | undefined {
		if (!marks || leftId === undefined) return undefined;
		return marks[leftId] ? 'right' : 'wrong';
	}

	/** Tap a left item: pick it, un-pick it, or send a placed one back. */
	function pickLeft(id: string) {
		if (matchOfLeft(id)) {
			matches = matches.filter((m) => m.left !== id);
			selectedLeft = null;
			announcement = `Undid match for ${plain(left.find((l) => l.id === id)?.label ?? id)}`;
			return;
		}
		selectedLeft = selectedLeft === id ? null : id;
	}

	function pickRight(id: string) {
		if (!selectedLeft) {
			// Tapping a placed right item returns it.
			matches = matches.filter((m) => m.right !== id);
			return;
		}
		pair(selectedLeft, id);
	}

	function pair(leftId: string, rightId: string) {
		matches = [
			...matches.filter((m) => m.left !== leftId && m.right !== rightId),
			{ left: leftId, right: rightId }
		];
		announcement = `Matched ${plain(left.find((l) => l.id === leftId)?.label ?? leftId)} with ${plain(labelOf(rightId))}`;
		selectedLeft = null;
	}

	function dragFor(leftId: string) {
		return {
			disabled: disabled || !!matchOfLeft(leftId),
			mouseOnly: true,
			onStart: () => (selectedLeft = leftId),
			onMove: (x: number, y: number) =>
				(hoverRight = targetAt(x, y, '[data-right-id]')?.dataset.rightId ?? null),
			onDrop: (x: number, y: number) => {
				const target = targetAt(x, y, '[data-right-id]')?.dataset.rightId;
				hoverRight = null;
				if (target) pair(leftId, target);
			},
			onCancel: () => (hoverRight = null)
		};
	}

	$effect(() => {
		response = { matches };
		progress = { done: matches.length, total: left.length };
	});
</script>

{#if !disabled}
	<p class="hint">Tap an item on the left, then tap its match on the right. Tap a matched item to undo.</p>
{/if}
<div class="columns">
	<div class="column">
		<ul class="col" aria-label="Items to match">
			{#each left as item, index (item.id)}
				{@const m = matchOfLeft(item.id)}
				{@const mark = markFor(item.id)}
				<li class="card" class:paired={!!m}>
					<span class="badge" aria-hidden="true">{index + 1}</span>
					<div class="main">
						<button
							type="button"
							class="option"
							class:selected={selectedLeft === item.id}
							class:matched={!!m}
							aria-pressed={selectedLeft === item.id || !!m}
							aria-describedby={m ? `${uid}-l-${index}` : undefined}
							data-mark={mark}
							{disabled}
							use:pointerDrag={dragFor(item.id)}
							onclick={() => pickLeft(item.id)}
						>
							<span><InlineMarkup value={item.label} /></span>
						</button>
						{#if m}
							<span class="pair-chip" data-testid="pair-chip" aria-hidden="true"
								>↔ {letterOf(m.right)} · {plain(labelOf(m.right))}</span
							>
							<span class="sr" id={`${uid}-l-${index}`}
								>{plain(item.label)}, matched with {plain(labelOf(m.right))}.{disabled ? '' : ' Tap to undo.'}</span
							>
						{/if}
					</div>
					{#if mark}<span class="result"><MarkBadge {mark} /></span>{/if}
				</li>
			{/each}
		</ul>
	</div>
	<div class="column">
		<ul class="col" aria-label="Matches">
			{#each right as item, index (item.id)}
				{@const m = matchOfRight(item.id)}
				{@const mark = markFor(m?.left)}
				<li class="card" class:paired={!!m}>
					<span class="badge letter" aria-hidden="true">{String.fromCharCode(65 + index)}</span>
					<div class="main">
						<button
							type="button"
							class="option"
							class:matched={!!m}
							class:drop-over={hoverRight === item.id}
							aria-pressed={!!m}
							aria-describedby={m ? `${uid}-r-${index}` : undefined}
							data-right-id={item.id}
							data-mark={mark}
							disabled={disabled || (!selectedLeft && !m)}
							onclick={() => pickRight(item.id)}
						>
							<span><InlineMarkup value={item.label} /></span>
						</button>
						{#if m}
							<span class="pair-chip" aria-hidden="true">↔ {numberOf(m.left)}</span>
							<span class="sr" id={`${uid}-r-${index}`}
								>Matched with item {numberOf(m.left)}.{disabled ? '' : ' Tap to undo.'}</span
							>
						{/if}
					</div>
					{#if mark}<span class="result"><MarkBadge {mark} /></span>{/if}
				</li>
			{/each}
		</ul>
	</div>
</div>
<p class="sr" aria-live="polite">{announcement}</p>

<style>
	.columns {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 16px;
	}
	.card {
		display: flex;
		align-items: flex-start;
		gap: 8px;
	}
	.badge {
		display: grid;
		place-items: center;
		flex: 0 0 28px;
		width: 28px;
		height: 28px;
		margin-top: 14px;
		border-radius: 50%;
		background: var(--ink, #1c2321);
		color: var(--surface, #fff);
		font-size: 14px;
		font-weight: 700;
	}
	.badge.letter {
		background: var(--sand, #f3eee3);
		color: var(--ink, #1c2321);
		border: 1px solid var(--rule-strong, #c9c3b5);
	}
	.main {
		flex: 1;
		min-width: 0;
		display: grid;
		gap: 4px;
	}
	.result {
		display: flex;
		margin-top: 16px;
	}
	.pair-chip {
		justify-self: start;
		padding: 4px 10px;
		border-radius: 999px;
		background: var(--green, #1b5e40);
		color: #fff;
		font-size: 13px;
		font-weight: 600;
	}
	.option.selected {
		box-shadow: 0 0 0 3px var(--green, #1b5e40);
	}
	.option.drop-over {
		box-shadow: 0 0 0 3px var(--action, #c2410c);
	}
	.option:not(:disabled) {
		touch-action: manipulation;
	}
	.option:global([data-dragging='true']) {
		opacity: 0.7;
		cursor: grabbing;
	}
	@media (max-width: 520px) {
		.columns {
			grid-template-columns: 1fr;
		}
	}
</style>
