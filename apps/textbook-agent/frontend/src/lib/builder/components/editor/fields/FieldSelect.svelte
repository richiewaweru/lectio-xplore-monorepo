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
	const str = $derived(String(value ?? ''));
	const showRequired = $derived(touched && schema.required && str.trim() === '');
</script>

<label class="field flex flex-col gap-1">
	<span class="text-sm font-medium text-slate-700">
		{schema.label}{schema.required ? ' *' : ''}
	</span>
	<select
		class="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
		class:border-red-500={showRequired}
		class:ring-1={showRequired}
		class:ring-red-500={showRequired}
		value={str}
		onchange={(e) => {
			touched = true;
			onchange(e.currentTarget.value);
		}}
		onblur={() => onfieldblur?.()}
	>
		{#each schema.options ?? [] as opt (opt.value)}
			<option value={opt.value}>{opt.label}</option>
		{/each}
	</select>
	{#if showRequired}
		<span class="text-xs text-red-600">Required</span>
	{/if}
</label>
