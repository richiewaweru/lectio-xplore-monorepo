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

	let raw = $state('');

	export function load(saved: LearnerResponse | null | undefined) {
		const v = saved?.value;
		raw = typeof v === 'number' || typeof v === 'string' ? String(v) : '';
	}
	export function reset() {
		raw = '';
	}
	export function keepCorrect(_results?: ItemResults) {
		raw = '';
	}

	untrack(() => load(initialResponse));

	$effect(() => {
		response = { value: Number(raw) };
		progress = { done: raw.trim().length > 0 && Number.isFinite(Number(raw)) ? 1 : 0, total: 1 };
	});
</script>

<label class="field">
	<span class="sr">Answer</span>
	<input
		type="number"
		aria-label="Answer"
		value={raw}
		{disabled}
		oninput={(e) => (raw = (e.currentTarget as HTMLInputElement).value)}
	/>
</label>
