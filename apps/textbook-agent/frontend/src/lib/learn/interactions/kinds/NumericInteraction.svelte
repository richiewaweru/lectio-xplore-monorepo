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
		config,
		disabled = false,
		itemResults: _itemResults = null,
		initialResponse = null,
		response = $bindable({}),
		progress = $bindable({ done: 0, total: 1 })
	}: Props = $props();

	const uid = $props.id();
	const unit = $derived(typeof config.unit === 'string' && config.unit.trim() ? config.unit.trim() : '');
	const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : undefined);
	const min = $derived(num(config.min));
	const max = $derived(num(config.max));
	const step = $derived(num(config.step) ?? 'any');

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

<div class="field">
	<label class="field-label" for={`${uid}-answer`}>Answer</label>
	<div class="entry">
		<input
			id={`${uid}-answer`}
			type="number"
			inputmode="decimal"
			{min}
			{max}
			{step}
			value={raw}
			aria-describedby={unit ? `${uid}-unit` : undefined}
			{disabled}
			oninput={(e) => (raw = (e.currentTarget as HTMLInputElement).value)}
		/>
		{#if unit}<span class="unit" id={`${uid}-unit`}>{unit}</span>{/if}
	</div>
</div>

<style>
	.entry {
		display: flex;
		align-items: center;
		gap: 10px;
		max-width: 320px;
	}
	.unit {
		font-weight: 600;
		white-space: nowrap;
	}
</style>
