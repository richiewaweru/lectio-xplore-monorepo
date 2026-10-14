<script lang="ts">
	import { untrack } from 'svelte';
	import InlineMarkup from '$lib/learn/document/renderers/InlineMarkup.svelte';
	import type { ItemResults, KindProgress, LearnerResponse } from '../types';
	import MarkBadge from './MarkBadge.svelte';
	import { pointerDrag } from './drag';
	import { listResults, sequenceItems } from './shared';

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

	const steps = $derived(sequenceItems(config));

	/** Starting order: the given items; never the solved order (preview configs carry it). */
	function startOrder(): string[] {
		const ids = steps.map((s) => s.id);
		const solved = Array.isArray(config.order) ? config.order.map(String) : null;
		if (ids.length > 1 && solved && solved.join('\u0000') === ids.join('\u0000')) {
			return [...ids.slice(1), ids[0]!];
		}
		return ids;
	}

	let order = $state<string[]>([]);
	const marks = $derived(listResults(itemResults));

	export function load(saved: LearnerResponse | null | undefined) {
		const o = saved?.order;
		const known = new Set(steps.map((s) => s.id));
		order =
			Array.isArray(o) && o.length === known.size && o.every((id) => known.has(String(id)))
				? o.map(String)
				: startOrder();
	}
	export function reset() {
		order = startOrder();
	}
	/** Items stay where they are; the learner rearranges the wrong ones. */
	export function keepCorrect(_results?: ItemResults) {}

	untrack(() => load(initialResponse));

	$effect(() => {
		if (order.length === 0 && steps.length > 0) order = startOrder();
	});

	function move(index: number, dir: -1 | 1) {
		const next = index + dir;
		if (next < 0 || next >= order.length) return;
		const copy = [...order];
		[copy[index], copy[next]] = [copy[next]!, copy[index]!];
		order = copy;
	}

	let list = $state<HTMLOListElement>();
	let draggingId = $state<string | null>(null);

	/** Pointer dragging a handle: slot the row where the pointer is. */
	function dragTo(id: string, y: number) {
		const rows = list ? [...list.children] : [];
		let target = rows.length - 1;
		for (let i = 0; i < rows.length; i++) {
			const r = rows[i]!.getBoundingClientRect();
			if (r.height > 0 && y < r.top + r.height / 2) {
				target = i;
				break;
			}
		}
		const from = order.indexOf(id);
		if (from < 0 || target < 0 || target === from) return;
		const copy = order.filter((x) => x !== id);
		copy.splice(target, 0, id);
		order = copy;
	}

	function handleFor(id: string) {
		return {
			disabled,
			threshold: 3,
			onStart: () => (draggingId = id),
			onMove: (_x: number, y: number) => dragTo(id, y),
			onDrop: () => (draggingId = null),
			onCancel: () => (draggingId = null)
		};
	}

	const labelFor = (id: string) => steps.find((s) => s.id === id)?.label ?? id;

	$effect(() => {
		response = { order };
		progress = { done: order.length, total: Math.max(order.length, steps.length) };
	});
</script>

<p class="hint">Use the arrows or drag the handle to put the steps in order.</p>
<ol class="steps" bind:this={list}>
	{#each order as id, index (id)}
		{@const mark = marks ? (marks[index] ? 'right' : 'wrong') : undefined}
		<li class:dragging={draggingId === id} data-mark={mark}>
			<span class="num" aria-hidden="true">{index + 1}</span>
			<span
				class="grip"
				class:off={disabled}
				data-testid="drag-handle"
				aria-hidden="true"
				use:pointerDrag={handleFor(id)}>⠿</span
			>
			<span class="label"><InlineMarkup value={labelFor(id)} /></span>
			<MarkBadge {mark} />
			<div class="moves">
				<button
					type="button"
					aria-label={`Move ${labelFor(id)} up`}
					disabled={disabled || index === 0}
					onclick={() => move(index, -1)}
				>
					↑
				</button>
				<button
					type="button"
					aria-label={`Move ${labelFor(id)} down`}
					disabled={disabled || index === order.length - 1}
					onclick={() => move(index, 1)}
				>
					↓
				</button>
			</div>
		</li>
	{/each}
</ol>

<style>
	li {
		display: flex;
		align-items: center;
		gap: 10px;
		min-height: 56px;
		border: 1px solid var(--rule-strong, #c9c3b5);
		border-radius: 10px;
		background: var(--surface, #fff);
		padding: 6px 8px 6px 10px;
	}
	li.dragging {
		box-shadow: 0 0 0 3px var(--action, #c2410c);
	}
	.num {
		display: grid;
		place-items: center;
		flex: 0 0 28px;
		width: 28px;
		height: 28px;
		border-radius: 50%;
		background: var(--ink, #1c2321);
		color: var(--surface, #fff);
		font-size: 14px;
		font-weight: 700;
	}
	.grip {
		display: grid;
		place-items: center;
		flex: 0 0 32px;
		align-self: stretch;
		font-size: 22px;
		line-height: 1;
		color: var(--ink, #1c2321);
		opacity: 0.55;
		cursor: grab;
		touch-action: none;
		user-select: none;
	}
	.grip.off {
		cursor: default;
		opacity: 0.25;
	}
	.label {
		flex: 1;
		min-width: 0;
	}
	.moves {
		display: flex;
		gap: 6px;
	}
	.moves button {
		width: 44px;
		height: 44px;
		border: 1px solid var(--rule-strong, #c9c3b5);
		border-radius: 8px;
		background: var(--surface, #fff);
		color: inherit;
		font: inherit;
		font-size: 18px;
		cursor: pointer;
	}
	.moves button:disabled {
		opacity: 0.35;
		cursor: default;
	}
</style>
