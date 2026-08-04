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

	const checked = $derived(Boolean(value));
</script>

<label class="field flex cursor-pointer items-center gap-2">
	<input
		type="checkbox"
		class="size-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
		{checked}
		onchange={(e) => onchange(e.currentTarget.checked)}
		onblur={() => onfieldblur?.()}
	/>
	<span class="text-sm font-medium text-slate-700">{schema.label}{schema.required ? ' *' : ''}</span>
</label>
