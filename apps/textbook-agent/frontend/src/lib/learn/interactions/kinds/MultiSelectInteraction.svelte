<script lang="ts">
	import { untrack } from 'svelte';
	import InlineMarkup from '$lib/learn/document/renderers/InlineMarkup.svelte';
	import type { ItemResults, KindProgress, LearnerResponse } from '../types';
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

<ul class="options" role="group" aria-label="Choose all that apply">
	{#each options as option (option.id)}
		<li>
			<button
				type="button"
				class="option"
				class:selected={selected.includes(option.id)}
				aria-pressed={selected.includes(option.id)}
				data-mark={markFor(option.id)}
				{disabled}
				onclick={() => toggle(option.id)}
			>
				<span class="option-letter" aria-hidden="true">{option.letter}</span>
				<span><InlineMarkup value={option.text} /></span>
			</button>
		</li>
	{/each}
</ul>
