<script lang="ts">
	import type { FieldSchema } from 'lectio';

	let {
		schema,
		value,
		onchange,
		onfieldblur
	}: {
		schema: FieldSchema;
		value: unknown;
		onchange: (value: unknown) => void;
		onfieldblur?: () => void;
	} = $props();

	let touched = $state(false);
	const num = $derived(typeof value === 'number' ? value : Number(value));
	const display = $derived(Number.isFinite(num) ? String(num) : '');
	const showRequired = $derived(touched && schema.required && !Number.isFinite(num));
</script>

<label class="field flex flex-col gap-1">
	<span class="text-sm font-medium text-slate-700">
		{schema.label}{schema.required ? ' *' : ''}
	</span>
	<input
		type="number"
		class="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
		class:border-red-500={showRequired}
		class:ring-1={showRequired}
		class:ring-red-500={showRequired}
		value={display}
		placeholder={schema.placeholder}
		oninput={(e) => {
			touched = true;
			const v = e.currentTarget.value;
			if (v === '') {
				onchange(NaN);
				return;
			}
			const n = Number(v);
			onchange(Number.isFinite(n) ? n : v);
		}}
		onblur={() => onfieldblur?.()}
	/>
	{#if showRequired}
		<span class="text-xs text-red-600">Required</span>
	{/if}
</label>
