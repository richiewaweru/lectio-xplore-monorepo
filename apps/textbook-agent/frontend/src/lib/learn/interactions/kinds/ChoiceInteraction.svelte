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

	let selected = $state<string | null>(null);
	const options = $derived(choiceOptions(config));
	const marks = $derived(mapResults(itemResults));

	export function load(saved: LearnerResponse | null | undefined) {
		const id = saved?.selected_option_id;
		selected = typeof id === 'string' && id ? id : null;
	}
	export function reset() {
		selected = null;
	}
	/** A wrong choice is simply cleared. */
	export function keepCorrect(_results?: ItemResults) {
		selected = null;
	}

	untrack(() => load(initialResponse));

	$effect(() => {
		response = { selected_option_id: selected };
		progress = { done: selected ? 1 : 0, total: 1 };
	});
</script>

<ul class="options" role="group" aria-label="Choose one">
	{#each options as option (option.id)}
		<li>
			<button
				type="button"
				class="option"
				class:selected={selected === option.id}
				aria-pressed={selected === option.id}
				data-mark={marks && selected === option.id ? (marks[option.id] ? 'right' : 'wrong') : undefined}
				{disabled}
				onclick={() => (selected = option.id)}
			>
				<span class="option-letter" aria-hidden="true">{option.letter}</span>
				<span><InlineMarkup value={option.text} /></span>
			</button>
		</li>
	{/each}
</ul>
