<script lang="ts">
	import type { FieldSchema } from 'lectio';
	import { sanitizeSvg } from '$lib/builder/utils/media-utils';

	let {
		schema,
		value,
		onchange,
		onfieldblur
	}: {
		schema: FieldSchema;
		value?: unknown;
		onchange?: (value: unknown) => void;
		onfieldblur?: () => void;
	} = $props();

	let draft = $state('');

	$effect(() => {
		draft = typeof value === 'string' ? value : '';
	});

	function commitSanitized(svg: string): void {
		const clean = sanitizeSvg(svg);
		onchange?.(clean);
	}

	function onPasteAreaBlur(): void {
		commitSanitized(draft);
		onfieldblur?.();
	}

	async function onSvgFile(e: Event): Promise<void> {
		const input = e.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		input.value = '';
		if (!file) return;
		if (!file.name.toLowerCase().endsWith('.svg') && file.type !== 'image/svg+xml') {
			return;
		}
		const text = await file.text();
		commitSanitized(text);
	}
</script>

<div class="field space-y-3 rounded-md border border-slate-200 bg-white p-4 text-sm">
	<label class="block font-medium text-slate-800" for="svg-paste-{schema.field}">
		{schema.label}{schema.required ? ' *' : ''}
	</label>
	<p class="text-xs text-slate-500">Paste SVG markup or upload an .svg file. Scripts and unsafe attributes are removed.</p>
	<textarea
		id="svg-paste-{schema.field}"
		class="min-h-[140px] w-full rounded-md border border-slate-300 px-2 py-1.5 font-mono text-xs"
		bind:value={draft}
		onblur={onPasteAreaBlur}
	></textarea>
	<div class="flex flex-wrap items-center gap-3">
		<label class="text-xs font-medium text-slate-600" for="svg-file-{schema.field}">Upload SVG</label>
		<input
			id="svg-file-{schema.field}"
			type="file"
			accept=".svg,image/svg+xml"
			class="text-xs text-slate-600 file:mr-2 file:rounded file:border file:border-slate-300 file:bg-slate-50 file:px-2 file:py-1"
			onchange={onSvgFile}
		/>
	</div>
	<button
		type="button"
		disabled
		class="cursor-not-allowed rounded-md border border-dashed border-slate-300 bg-slate-50 px-3 py-2 text-xs text-slate-400"
		title="Coming in Phase 5"
	>
		Generate with AI
	</button>
</div>
