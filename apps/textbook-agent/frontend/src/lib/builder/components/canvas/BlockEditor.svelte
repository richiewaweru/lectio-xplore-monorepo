<script lang="ts">
	import type { EditSchema, FieldSchema } from 'lectio';
	import type { Component } from 'svelte';
	import { setDocumentStoreContext } from '$lib/builder/components/editor/document-store-context';
	import type { DocumentStore } from '$lib/builder/stores/document.svelte';
	import FieldBoolean from '$lib/builder/components/editor/fields/FieldBoolean.svelte';
	import FieldList from '$lib/builder/components/editor/fields/FieldList.svelte';
	import FieldMedia from '$lib/builder/components/editor/fields/FieldMedia.svelte';
	import FieldNumber from '$lib/builder/components/editor/fields/FieldNumber.svelte';
	import FieldObjectList from '$lib/builder/components/editor/fields/FieldObjectList.svelte';
	import FieldRichText from '$lib/builder/components/editor/fields/FieldRichText.svelte';
	import FieldSelect from '$lib/builder/components/editor/fields/FieldSelect.svelte';
	import FieldSvg from '$lib/builder/components/editor/fields/FieldSvg.svelte';
	import FieldText from '$lib/builder/components/editor/fields/FieldText.svelte';
	import FieldTextarea from '$lib/builder/components/editor/fields/FieldTextarea.svelte';
	import { isDiagramComponentId, svgFieldFor } from './diagram-media-fields';

	let {
		schema,
		content,
		onchange,
		onfieldblur,
		store
	}: {
		schema: EditSchema;
		content: Record<string, unknown>;
		onchange: (field: string, value: unknown) => void;
		onfieldblur?: () => void;
		store: DocumentStore;
	} = $props();

	$effect.pre(() => {
		setDocumentStoreContext(store);
	});

	const BY_INPUT: Record<string, Component> = {
		text: FieldText as Component,
		textarea: FieldTextarea as Component,
		richtext: FieldRichText as Component,
		select: FieldSelect as Component,
		number: FieldNumber as Component,
		boolean: FieldBoolean as Component,
		list: FieldList as Component,
		'object-list': FieldObjectList as Component,
		media: FieldMedia as Component,
		svg: FieldSvg as Component
	};

	function fieldVisible(f: FieldSchema): boolean {
		if (f.input === 'hidden') return false;
		if (f.field === 'quote_attribution' && content.type !== 'quote') return false;
		return true;
	}

	const visibleFields = $derived(schema.fields.filter(fieldVisible));

	const ownerId = $derived(schema.component_id);
</script>

<div class="editor-form block-editor-form space-y-4 p-2 lg:p-4">
	{#if schema.component_id === 'image-block' && !(typeof content.alt_text === 'string' && content.alt_text.trim())}
		<p class="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
			Add alt text for accessibility.
		</p>
	{/if}
	{#each visibleFields as fieldSchema (fieldSchema.field)}
		{@const FieldComponent = BY_INPUT[fieldSchema.input]}
		{#if fieldSchema.input === 'media'}
			<FieldMedia
				schema={fieldSchema}
				value={content[fieldSchema.field]}
				onchange={(v: unknown) => onchange(fieldSchema.field, v)}
				onSvgChange={(svg: string) => {
					if (!isDiagramComponentId(ownerId)) return;
					const svgField = svgFieldFor(ownerId, fieldSchema.field);
					if (svgField) onchange(svgField, svg);
				}}
				{onfieldblur}
				ownerComponentId={ownerId}
			/>
		{:else if fieldSchema.input === 'object-list'}
			<FieldObjectList
				schema={fieldSchema}
				value={content[fieldSchema.field]}
				onchange={(v: unknown) => onchange(fieldSchema.field, v)}
				{onfieldblur}
				ownerComponentId={ownerId}
			/>
		{:else if FieldComponent}
			<FieldComponent
				schema={fieldSchema}
				value={content[fieldSchema.field]}
				onchange={(v: unknown) => onchange(fieldSchema.field, v)}
				{onfieldblur}
			/>
		{:else}
			<p class="text-xs text-amber-600">Unsupported field type: {fieldSchema.input}</p>
		{/if}
	{/each}
</div>
