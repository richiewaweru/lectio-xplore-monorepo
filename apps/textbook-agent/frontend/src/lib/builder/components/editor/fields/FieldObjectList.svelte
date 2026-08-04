<script lang="ts">
	import type { FieldSchema } from 'lectio';
	import type { Component } from 'svelte';
	import { emptyObjectFromItemSchema } from './field-empty';
	import FieldBoolean from './FieldBoolean.svelte';
	import FieldList from './FieldList.svelte';
	import FieldMedia from './FieldMedia.svelte';
	import FieldNumber from './FieldNumber.svelte';
	import FieldRichText from './FieldRichText.svelte';
	import FieldSelect from './FieldSelect.svelte';
	import FieldSvg from './FieldSvg.svelte';
	import FieldText from './FieldText.svelte';
	import FieldTextarea from './FieldTextarea.svelte';
	import Self from './FieldObjectList.svelte';

	let {
		schema,
		value,
		onchange,
		onfieldblur,
		onSvgChange,
		ownerComponentId = ''
	}: {
		schema: FieldSchema;
		value: unknown;
		onchange: (value: unknown) => void;
		onfieldblur?: () => void;
		onSvgChange?: (svg: string) => void;
		ownerComponentId?: string;
	} = $props();

	const BY_INPUT: Record<string, Component> = {
		text: FieldText as Component,
		textarea: FieldTextarea as Component,
		richtext: FieldRichText as Component,
		select: FieldSelect as Component,
		number: FieldNumber as Component,
		boolean: FieldBoolean as Component,
		list: FieldList as Component,
		'object-list': Self as Component,
		media: FieldMedia as Component,
		svg: FieldSvg as Component
	};

	const items = $derived(
		Array.isArray(value) ? (value as Record<string, unknown>[]) : []
	);
	const maxItems = $derived(schema.maxItems);
	const atMax = $derived(maxItems !== undefined && items.length >= maxItems);
	const itemFields = $derived(schema.itemSchema ?? []);

	function setItems(next: Record<string, unknown>[]): void {
		onchange(next);
	}

	function patch(i: number, field: string, v: unknown): void {
		const next = items.map((row, idx) => (idx === i ? { ...row, [field]: v } : row));
		setItems(next);
	}

	function addItem(): void {
		if (atMax) return;
		const empty = emptyObjectFromItemSchema(itemFields);
		setItems([...items, empty]);
	}

	function removeItem(i: number): void {
		setItems(items.filter((_, j) => j !== i));
	}

	function moveItem(i: number, dir: -1 | 1): void {
		const j = i + dir;
		if (j < 0 || j >= items.length) return;
		const next = [...items];
		[next[i], next[j]] = [next[j]!, next[i]!];
		setItems(next);
	}
</script>

<div class="field flex flex-col gap-3">
	<span class="text-sm font-medium text-slate-700">
		{schema.label}{schema.required ? ' *' : ''}
	</span>
	{#if maxItems !== undefined}
		<p class="text-xs text-slate-500">{items.length}/{maxItems} items</p>
	{/if}
	<div class="space-y-4">
		{#each items as row, i (i)}
			<div class="space-y-3 rounded-lg border border-slate-200 bg-slate-50/90 p-3">
				<div class="flex flex-wrap justify-end gap-2">
					<button
						type="button"
						class="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-40"
						disabled={i === 0}
						onclick={() => moveItem(i, -1)}
					>
						Up
					</button>
					<button
						type="button"
						class="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-40"
						disabled={i === items.length - 1}
						onclick={() => moveItem(i, 1)}
					>
						Down
					</button>
					<button
						type="button"
						class="rounded border border-red-200 bg-white px-2 py-1 text-xs text-red-700 hover:bg-red-50"
						onclick={() => removeItem(i)}
					>
						Remove
					</button>
				</div>
				{#each itemFields as sub (sub.field)}
					{#if sub.input !== 'hidden'}
						{@const FieldComponent = BY_INPUT[sub.input]}
						{#if sub.input === 'media'}
							<FieldMedia
								schema={sub}
								value={row[sub.field]}
								onchange={(v: unknown) => patch(i, sub.field, v)}
								onSvgChange={(svg: string) => {
									const svgField = sub.field === 'media_id' ? 'svg_content' : null;
									if (svgField) patch(i, svgField, svg);
									onSvgChange?.(svg);
								}}
								{onfieldblur}
								{ownerComponentId}
							/>
						{:else if sub.input === 'object-list'}
							<Self
								schema={sub}
								value={row[sub.field]}
								onchange={(v: unknown) => patch(i, sub.field, v)}
								{onSvgChange}
								{onfieldblur}
								{ownerComponentId}
							/>
						{:else if FieldComponent}
							<FieldComponent
								schema={sub}
								value={row[sub.field]}
								onchange={(v: unknown) => patch(i, sub.field, v)}
								{onfieldblur}
							/>
						{:else}
							<p class="text-xs text-amber-600">Unsupported field type: {sub.input}</p>
						{/if}
					{/if}
				{/each}
			</div>
		{/each}
	</div>
	<button
		type="button"
		class="w-fit rounded-md bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
		disabled={atMax}
		onclick={addItem}
	>
		Add
	</button>
</div>
