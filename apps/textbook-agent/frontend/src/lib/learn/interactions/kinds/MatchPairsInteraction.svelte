<script lang="ts">
	import { untrack } from 'svelte';
	import InlineMarkup from '$lib/learn/document/renderers/InlineMarkup.svelte';
	import type { ItemResults, KindProgress, LearnerResponse } from '../types';
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

	let selectedLeft = $state<string | null>(null);
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

	function markFor(leftId: string | undefined): 'right' | 'wrong' | undefined {
		if (!marks || leftId === undefined) return undefined;
		return marks[leftId] ? 'right' : 'wrong';
	}

	/** Tap a left item: pick it, un-pick it, or send a placed one back. */
	function pickLeft(id: string) {
		if (matchOfLeft(id)) {
			matches = matches.filter((m) => m.left !== id);
			selectedLeft = null;
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
		matches = [
			...matches.filter((m) => m.left !== selectedLeft && m.right !== id),
			{ left: selectedLeft, right: id }
		];
		selectedLeft = null;
	}

	$effect(() => {
		response = { matches };
		progress = { done: matches.length, total: left.length };
	});
</script>

<div class="columns">
	<ul class="col">
		{#each left as item (item.id)}
			<li>
				<button
					type="button"
					class="option"
					class:selected={selectedLeft === item.id}
					class:matched={!!matchOfLeft(item.id)}
					aria-pressed={selectedLeft === item.id || !!matchOfLeft(item.id)}
					data-mark={markFor(item.id)}
					{disabled}
					onclick={() => pickLeft(item.id)}
				>
					<span><InlineMarkup value={item.label} /></span>
					{#if matchOfLeft(item.id)}
						<span class="placed-note" aria-hidden="true">→ {labelOf(matchOfLeft(item.id)!.right)}</span>
					{/if}
				</button>
			</li>
		{/each}
	</ul>
	<ul class="col">
		{#each right as item (item.id)}
			<li>
				<button
					type="button"
					class="option"
					class:matched={!!matchOfRight(item.id)}
					aria-pressed={!!matchOfRight(item.id)}
					data-mark={markFor(matchOfRight(item.id)?.left)}
					disabled={disabled || (!selectedLeft && !matchOfRight(item.id))}
					onclick={() => pickRight(item.id)}
				>
					<span><InlineMarkup value={item.label} /></span>
				</button>
			</li>
		{/each}
	</ul>
</div>
