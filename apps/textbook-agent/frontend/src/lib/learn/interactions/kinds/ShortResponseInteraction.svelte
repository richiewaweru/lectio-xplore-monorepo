<script lang="ts">
	import { untrack } from 'svelte';
	import type { ItemResults, KindProgress, LearnerResponse } from '../types';

	interface Props {
		config: Record<string, unknown>;
		disabled?: boolean;
		itemResults?: ItemResults | undefined;
		initialResponse?: LearnerResponse | null;
		response?: LearnerResponse;
		progress?: KindProgress;
	}

	let {
		config: _config,
		disabled = false,
		itemResults: _itemResults = null,
		initialResponse = null,
		response = $bindable({}),
		progress = $bindable({ done: 0, total: 1 })
	}: Props = $props();

	let text = $state('');

	export function load(saved: LearnerResponse | null | undefined) {
		const t = saved?.text;
		text = typeof t === 'string' ? t : '';
	}
	export function reset() {
		text = '';
	}
	export function keepCorrect(_results?: ItemResults) {
		text = '';
	}

	untrack(() => load(initialResponse));

	$effect(() => {
		response = { text };
		progress = { done: text.trim().length > 0 ? 1 : 0, total: 1 };
	});
</script>

<label class="field">
	<span class="sr">Answer</span>
	<input type="text" aria-label="Answer" bind:value={text} {disabled} />
</label>
