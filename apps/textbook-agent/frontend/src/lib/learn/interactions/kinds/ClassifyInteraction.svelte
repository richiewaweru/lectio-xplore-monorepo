<script lang="ts">
	import { untrack } from 'svelte';
	import InlineMarkup from '$lib/learn/document/renderers/InlineMarkup.svelte';
	import type { ItemResults, KindProgress, LearnerResponse } from '../types';
	import MarkBadge from './MarkBadge.svelte';
	import { pointerDrag, targetAt } from './drag';
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
	let hoverGroup = $state<string | null>(null);
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

	const plain = (v: string) => v.replace(/[*_~^`]/g, '');
	const itemLabel = (id: string) => plain(items.find((i) => i.id === id)?.label ?? id);
	const unplaced = $derived(items.filter((i) => !matches.some((m) => m.left === i.id)));
	const placedIn = (catId: string) =>
		matches.filter((m) => m.right === catId).map((m) => items.find((i) => i.id === m.left)!).filter(Boolean);

	/** Tap a pool item: pick it or un-pick it. */
	function pickItem(id: string) {
		selected = selected === id ? null : id;
	}

	function place(itemId: string, catId: string) {
		matches = [...matches.filter((m) => m.left !== itemId), { left: itemId, right: catId }];
		announcement = `Placed ${itemLabel(itemId)} in ${plain(categoryLabel(catId))}`;
		selected = null;
	}

	function pickCategory(id: string) {
		if (!selected) return;
		place(selected, id);
	}

	function remove(itemId: string) {
		const from = placement(itemId)?.right;
		matches = matches.filter((m) => m.left !== itemId);
		selected = null;
		announcement = `Returned ${itemLabel(itemId)} to items${from ? ` from ${plain(categoryLabel(from))}` : ''}`;
	}

	function dragFor(itemId: string) {
		return {
			disabled,
			mouseOnly: true,
			onStart: () => (selected = itemId),
			onMove: (x: number, y: number) =>
				(hoverGroup = targetAt(x, y, '[data-group-id]')?.dataset.groupId ?? null),
			onDrop: (x: number, y: number) => {
				const target = targetAt(x, y, '[data-group-id]')?.dataset.groupId;
				hoverGroup = null;
				if (target) place(itemId, target);
			},
			onCancel: () => (hoverGroup = null)
		};
	}

	$effect(() => {
		response = { matches };
		progress = { done: matches.length, total: items.length };
	});
</script>

<div class="pool" data-testid="classify-pool">
	<p class="label">Items</p>
	<ul class="chips" aria-label="Items to sort">
		{#each unplaced as item (item.id)}
			<li>
				<button
					type="button"
					class="chip"
					class:selected={selected === item.id}
					aria-pressed={selected === item.id}
					{disabled}
					use:pointerDrag={dragFor(item.id)}
					onclick={() => pickItem(item.id)}
				>
					<span><InlineMarkup value={item.label} /></span>
				</button>
			</li>
		{:else}
			<li class="hint">All items are sorted.</li>
		{/each}
	</ul>
	{#if !disabled}
		<p class="hint">Tap an item, then tap the group it belongs in.</p>
	{/if}
</div>
<div class="groups">
	{#each categories as cat (cat.id)}
		{@const inside = placedIn(cat.id)}
		<!-- Tapping empty space in the box is a mouse convenience; the header button is the keyboard path. -->
		<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
		<div
			class="group"
			class:armed={!!selected}
			class:drop-over={hoverGroup === cat.id}
			data-group-id={cat.id}
			data-testid="classify-group"
			onclick={(e) => {
				if (!(e.target as HTMLElement).closest('button')) pickCategory(cat.id);
			}}
		>
			<button
				type="button"
				class="chip group-btn"
				disabled={disabled || !selected}
				onclick={() => pickCategory(cat.id)}
			>
				<span><InlineMarkup value={cat.label} /></span>
			</button>
			<ul class="chips placed" aria-label={`${plain(cat.label)}: placed items`}>
				{#each inside as item (item.id)}
					{@const mark = marks ? (marks[item.id] ? 'right' : 'wrong') : undefined}
					<li class="chip matched" data-testid="placed-chip" data-mark={mark}>
						<span><InlineMarkup value={item.label} /></span>
						<MarkBadge {mark} />
						{#if !disabled}
						<button
							type="button"
							class="remove"
							aria-label={`Remove ${plain(item.label)} from ${plain(cat.label)}`}
							{disabled}
							onclick={() => remove(item.id)}
						>
							<span aria-hidden="true">✕</span>
						</button>
						{/if}
					</li>
				{/each}
			</ul>
		</div>
	{/each}
</div>
<p class="sr" aria-live="polite" data-testid="classify-live">{announcement}</p>

<style>
	.pool {
		display: grid;
		gap: 8px;
		padding: 12px;
		border: 1px dashed var(--rule-strong, #c9c3b5);
		border-radius: 12px;
		background: var(--paper, #fafaf9);
	}
	.label {
		margin: 0;
		font-size: 13px;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}
	.chips {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.groups {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 12px;
	}
	.group {
		display: grid;
		align-content: start;
		gap: 10px;
		min-height: 120px;
		padding: 12px;
		border: 2px solid var(--rule-strong, #c9c3b5);
		border-radius: 12px;
		background: var(--surface, #fff);
	}
	.group.armed {
		border-color: var(--green, #1b5e40);
		border-style: dashed;
	}
	.group.drop-over {
		border-color: var(--action, #c2410c);
		background: var(--sand, #f3eee3);
	}
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-height: 44px;
		box-sizing: border-box;
		border: 1px solid var(--rule-strong, #c9c3b5);
		border-radius: 999px;
		background: var(--surface, #fff);
		padding: 8px 14px;
		color: inherit;
		font: inherit;
	}
	button.chip {
		cursor: pointer;
		touch-action: manipulation;
	}
	button.chip:disabled {
		cursor: default;
	}
	button.chip:global([data-dragging='true']) {
		opacity: 0.7;
		cursor: grabbing;
	}
	.chip.selected {
		border-color: var(--green, #1b5e40);
		background: var(--sand, #f3eee3);
		box-shadow: 0 0 0 3px var(--green, #1b5e40);
	}
	.group-btn {
		justify-self: stretch;
		justify-content: center;
		border-radius: 8px;
		font-weight: 700;
	}
	.placed .chip {
		padding-right: 6px;
	}
	.placed .chip:not([data-mark]) {
		border-color: var(--green, #1b5e40);
		background: var(--sand, #f3eee3);
	}
	.remove {
		display: grid;
		place-items: center;
		min-width: 44px;
		min-height: 44px;
		margin: -8px -6px -8px 0;
		border: 0;
		border-radius: 50%;
		background: transparent;
		color: inherit;
		font: inherit;
		cursor: pointer;
	}
	.remove:disabled {
		cursor: default;
		opacity: 0.4;
	}
</style>
