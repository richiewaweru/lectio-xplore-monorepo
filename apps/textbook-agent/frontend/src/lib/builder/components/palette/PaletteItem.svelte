<script lang="ts">
	import type { ComponentMeta } from 'lectio';

	let {
		meta,
		onadd
	}: {
		meta: ComponentMeta;
		onadd: (componentId: string) => void;
	} = $props();
</script>

<div
	class="palette-item flex flex-col gap-1 rounded-lg border border-slate-100 bg-slate-50/80 px-3 py-2"
	data-testid="palette-item"
	data-component-id={meta.id}
>
	<span class="font-medium text-sm text-slate-900">{meta.teacherLabel}</span>
	<span class="line-clamp-2 text-xs text-slate-500">{meta.teacherDescription}</span>
	<button
		type="button"
		class="mt-1 self-start rounded border border-slate-300 bg-white px-2 py-0.5 text-xs font-medium text-slate-700 hover:bg-slate-100"
		data-testid="palette-add-btn"
		onclick={() => onadd(meta.id)}
	>
		+ Add
	</button>
</div>
