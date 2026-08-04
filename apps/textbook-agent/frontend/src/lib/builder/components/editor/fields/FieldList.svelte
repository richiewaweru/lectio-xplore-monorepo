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

	const items = $derived(
		Array.isArray(value) ? (value as unknown[]).map((v) => String(v ?? '')) : []
	);
	const maxItems = $derived(schema.maxItems);
	const atMax = $derived(maxItems !== undefined && items.length >= maxItems);
	const showRequired = $derived(touched && schema.required && items.length === 0);

	function setItems(next: string[]): void {
		touched = true;
		onchange(next);
	}

	function updateAt(i: number, s: string): void {
		const next = [...items];
		next[i] = s;
		setItems(next);
	}

	function addRow(): void {
		if (atMax) return;
		setItems([...items, '']);
	}

	function removeRow(i: number): void {
		setItems(items.filter((_, j) => j !== i));
	}
</script>

<div class="field flex flex-col gap-2">
	<span class="text-sm font-medium text-slate-700">
		{schema.label}{schema.required ? ' *' : ''}
	</span>
	<ul class="space-y-2">
		{#each items as row, i (i)}
			<li class="flex gap-2">
				<input
					type="text"
					class="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
					class:border-red-500={showRequired}
					value={row}
					placeholder={schema.placeholder}
					oninput={(e) => updateAt(i, e.currentTarget.value)}
					onblur={() => onfieldblur?.()}
				/>
				<button
					type="button"
					class="shrink-0 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
					onclick={() => removeRow(i)}
				>
					Remove
				</button>
			</li>
		{/each}
	</ul>
	{#if maxItems !== undefined}
		<p class="text-xs text-slate-500">{items.length}/{maxItems} items</p>
	{/if}
	<button
		type="button"
		class="w-fit rounded-md bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
		disabled={atMax}
		onclick={addRow}
	>
		Add
	</button>
	{#if showRequired}
		<span class="text-xs text-red-600">Required</span>
	{/if}
</div>
