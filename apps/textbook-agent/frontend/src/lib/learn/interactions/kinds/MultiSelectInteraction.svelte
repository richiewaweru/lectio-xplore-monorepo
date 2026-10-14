<script lang="ts">
	import { untrack } from 'svelte';
	import InlineMarkup from '$lib/learn/document/renderers/InlineMarkup.svelte';
	import type { ItemResults, KindProgress, LearnerResponse } from '../types';
	import MarkBadge from './MarkBadge.svelte';
	import { choiceOptions, mapResults } from './shared';

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

	let selected = $state<string[]>([]);
	const options = $derived(choiceOptions(config));
	const marks = $derived(mapResults(itemResults));

	export function load(saved: LearnerResponse | null | undefined) {
		const ids = saved?.selected_option_ids;
		selected = Array.isArray(ids) ? ids.map(String) : [];
	}
	export function reset() {
		selected = [];
	}
	/** Keep the picks that were right; drop the wrong ones. */
	export function keepCorrect(results?: ItemResults) {
		const map = mapResults(results);
		selected = map ? selected.filter((id) => map[id] === true) : [];
	}

	untrack(() => load(initialResponse));

	function toggle(id: string) {
		selected = selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id];
	}

	function markFor(id: string): 'right' | 'wrong' | 'missed' | undefined {
		if (!marks) return undefined;
		if (selected.includes(id)) return marks[id] ? 'right' : 'wrong';
		return marks[id] === false ? 'missed' : undefined;
	}

	$effect(() => {
		response = { selected_option_ids: selected };
		progress = { done: selected.length > 0 ? 1 : 0, total: 1 };
	});
</script>

<p class="hint" data-testid="multi-hint">Choose all that apply</p>
<ul class="options" role="group" aria-label="Choose all that apply">
	{#each options as option (option.id)}
		{@const on = selected.includes(option.id)}
		{@const mark = markFor(option.id)}
		<li class="row">
			<button
				type="button"
				role="checkbox"
				class="option"
				class:selected={on}
				class:has-mark={!!mark}
				aria-checked={on}
				data-mark={mark}
				{disabled}
				onclick={() => toggle(option.id)}
			>
				<span class="box" aria-hidden="true">{on ? '✓' : ''}</span>
				<span class="option-letter" aria-hidden="true">{option.letter}</span>
				<span><InlineMarkup value={option.text} /></span>
			</button>
			{#if mark}<span class="badge"><MarkBadge {mark} /></span>{/if}
		</li>
	{/each}
</ul>

<style>
	.row {
		position: relative;
	}
	.box {
		display: grid;
		place-items: center;
		flex: 0 0 24px;
		width: 24px;
		height: 24px;
		box-sizing: border-box;
		border: 2px solid var(--ink, #1c2321);
		border-radius: 5px;
		background: var(--surface, #fff);
		color: #fff;
		font-size: 16px;
		font-weight: 800;
		line-height: 1;
	}
	.selected .box {
		background: var(--green, #1b5e40);
		border-color: var(--green, #1b5e40);
	}
	.option-letter {
		flex: 0 0 auto;
		min-width: 1.2em;
		font-weight: 700;
		opacity: 0.7;
	}
	.has-mark {
		padding-right: 48px;
	}
	.badge {
		position: absolute;
		right: 12px;
		top: 50%;
		transform: translateY(-50%);
		display: flex;
	}
</style>
