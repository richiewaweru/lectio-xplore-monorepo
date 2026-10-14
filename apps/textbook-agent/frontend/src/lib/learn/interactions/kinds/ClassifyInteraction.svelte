<script lang="ts">
	import { untrack } from 'svelte';
	import InlineMarkup from '$lib/learn/document/renderers/InlineMarkup.svelte';
	import type { ItemResults, KindProgress, LearnerResponse } from '../types';
	import { mapResults, toChoice } from './shared';

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
	const categories = $derived(
		Array.isArray(config.categories)
			? (config.categories as unknown[]).map(toChoice)
			: [...new Set(pairList.map((p) => p.right))].map((id) => ({ id, label: id }))
	);
	const items = $derived(
		Array.isArray(config.items)
			? (config.items as unknown[]).map(toChoice)
			: pairList.map((p) => ({ id: p.left, label: p.left }))
	);

	let selected = $state<string | null>(null);
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
		selected = null;
	}
	export function reset() {
		matches = [];
		selected = null;
	}
	/** Keep the items that landed in the right group; return the wrong ones. */
	export function keepCorrect(results?: ItemResults) {
		const map = mapResults(results);
		matches = map ? matches.filter((m) => map[m.left] === true) : [];
		selected = null;
	}

	untrack(() => load(initialResponse));

	const placement = (id: string) => matches.find((m) => m.left === id);
	const categoryLabel = (id: string) => categories.find((c) => c.id === id)?.label ?? id;

	/** Tap an item: pick it, un-pick it, or send a placed one back. */
	function pickItem(id: string) {
		if (placement(id)) {
			matches = matches.filter((m) => m.left !== id);
			selected = null;
			return;
		}
		selected = selected === id ? null : id;
	}

	function pickCategory(id: string) {
		if (!selected) return;
		matches = [...matches.filter((m) => m.left !== selected), { left: selected, right: id }];
		selected = null;
	}

	$effect(() => {
		response = { matches };
		progress = { done: matches.length, total: items.length };
	});
</script>

<ul class="chips">
	{#each items as item (item.id)}
		<li>
			<button
				type="button"
				class="chip"
				class:selected={selected === item.id}
				class:matched={!!placement(item.id)}
				data-mark={marks && placement(item.id) ? (marks[item.id] ? 'right' : 'wrong') : undefined}
				{disabled}
				onclick={() => pickItem(item.id)}
			>
				<span><InlineMarkup value={item.label} /></span>
				{#if placement(item.id)}
					<span class="placed-note" aria-hidden="true">→ {categoryLabel(placement(item.id)!.right)}</span>
				{/if}
			</button>
		</li>
	{/each}
</ul>
<ul class="chips">
	{#each categories as cat (cat.id)}
		<li>
			<button
				type="button"
				class="chip"
				disabled={disabled || !selected}
				onclick={() => pickCategory(cat.id)}
			>
				<span><InlineMarkup value={cat.label} /></span>
			</button>
		</li>
	{/each}
</ul>
