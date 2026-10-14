<script lang="ts">
	import { untrack } from 'svelte';
	import InlineMarkup from '$lib/learn/document/renderers/InlineMarkup.svelte';
	import type { ItemResults, KindProgress, LearnerResponse } from '../types';
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

	const labelFor = (id: string) => steps.find((s) => s.id === id)?.label ?? id;

	$effect(() => {
		response = { order };
		progress = { done: order.length, total: Math.max(order.length, steps.length) };
	});
</script>

<ol class="steps">
	{#each order as id, index (id)}
		<li data-mark={marks ? (marks[index] ? 'right' : 'wrong') : undefined}>
			<span><InlineMarkup value={labelFor(id)} /></span>
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
