<script lang="ts">
	import type { FieldSchema } from 'lectio';
	import { countWords } from './word-count';

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
	const str = $derived(String(value ?? ''));
	const words = $derived(countWords(str));
	const overCapacity = $derived(
		schema.maxWords !== undefined && words > schema.maxWords
	);
	const showRequired = $derived(touched && schema.required && str.trim() === '');
</script>

<label class="field flex flex-col gap-1">
	<span class="text-sm font-medium text-slate-700">
		{schema.label}{schema.required ? ' *' : ''}
	</span>
	<input
		type="text"
		class="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
		class:border-red-500={showRequired}
		class:ring-1={showRequired}
		class:ring-red-500={showRequired}
		value={str}
		placeholder={schema.placeholder}
		oninput={(e) => {
			touched = true;
			onchange(e.currentTarget.value);
		}}
		onblur={() => onfieldblur?.()}
	/>
	{#if schema.maxWords !== undefined}
		<span class="text-xs" class:text-amber-700={overCapacity} class:text-slate-500={!overCapacity}>
			{words}/{schema.maxWords} words
			{#if overCapacity}
				— exceeds recommended limit
			{/if}
		</span>
	{/if}
	{#if showRequired}
		<span class="text-xs text-red-600">Required</span>
	{/if}
</label>
