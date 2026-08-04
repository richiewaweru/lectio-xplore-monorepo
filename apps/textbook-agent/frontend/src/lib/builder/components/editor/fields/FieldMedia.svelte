<script lang="ts">
	import type { FieldSchema, MediaReference } from 'lectio';
	import { isDiagramComponentId } from '$lib/builder/components/canvas/diagram-media-fields';
	import { getDocumentStoreContext } from '$lib/builder/components/editor/document-store-context';
	import DiagramUploader from '$lib/builder/components/media/DiagramUploader.svelte';
	import ImageUploader from '$lib/builder/components/media/ImageUploader.svelte';
	import MediaGrid from '$lib/builder/components/media/MediaGrid.svelte';
	import VideoUrlInput from '$lib/builder/components/media/VideoUrlInput.svelte';

	let {
		schema,
		value,
		onchange,
		onSvgChange,
		ownerComponentId = ''
	}: {
		schema: FieldSchema;
		value?: unknown;
		onchange?: (value: unknown) => void;
		onSvgChange?: (svg: string) => void;
		onfieldblur?: () => void;
		/** Parent block component id - selects video vs image behaviour for this field. */
		ownerComponentId?: string;
	} = $props();

	const store = getDocumentStoreContext();

	const mediaId = $derived(typeof value === 'string' ? value : '');
	const wantVideo = $derived(ownerComponentId === 'video-embed');
	const wantImage = $derived(ownerComponentId === 'image-block');
	const wantDiagram = $derived(isDiagramComponentId(ownerComponentId));

	const docMedia = $derived(store?.document?.media ?? {});
	const current = $derived(mediaId ? docMedia[mediaId] : undefined);

	function pickMedia(id: string): void {
		onchange?.(id);
	}

	function addVideoFromEmbed(embedUrl: string): void {
		if (!store) return;
		const media: MediaReference = {
			id: crypto.randomUUID(),
			type: 'video',
			url: embedUrl,
			print_fallback: 'thumbnail'
		};
		store.addMedia(media);
		onchange?.(media.id);
	}

	function addImageFromUpload(payload: { url: string; filename: string; mimeType: string }): void {
		if (!store) return;
		const media: MediaReference = {
			id: crypto.randomUUID(),
			type: 'image',
			url: payload.url,
			filename: payload.filename,
			mime_type: payload.mimeType,
			alt_text: '',
			print_fallback: 'thumbnail'
		};
		store.addMedia(media);
		onchange?.(media.id);
	}

	function clearSelection(): void {
		onchange?.('');
	}
</script>

<div class="field space-y-4 rounded-md border border-slate-200 bg-white p-4 text-sm">
	<div>
		<p class="font-medium text-slate-800">
			{schema.label}{schema.required ? ' *' : ''}
		</p>
		{#if schema.help}
			<p class="mt-0.5 text-xs text-slate-500">{schema.help}</p>
		{/if}
	</div>

	{#if !store}
		<p class="text-amber-700">Editor not connected to document (internal error).</p>
	{:else}
		<div class="rounded-md border border-slate-100 bg-slate-50/80 p-3">
			<p class="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Current</p>
			{#if current}
				<div class="space-y-2">
					{#if current.type === 'video'}
						<div class="aspect-video w-full max-w-md overflow-hidden rounded border border-slate-200 bg-black/5">
							<iframe
								class="h-full w-full"
								title="Selected video"
								src={current.url}
								allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
								allowfullscreen
							></iframe>
						</div>
					{:else if current.type === 'image'}
						<img
							src={current.url}
							alt={current.alt_text ?? ''}
							class="max-h-48 max-w-full rounded border border-slate-200 object-contain"
						/>
					{:else}
						<p class="text-slate-600">Audio / other media selected.</p>
					{/if}
					<button
						type="button"
						class="text-xs font-medium text-blue-600 hover:text-blue-800"
						onclick={clearSelection}
					>
						Clear selection
					</button>
				</div>
			{:else}
				<p class="text-slate-500">Nothing selected yet.</p>
			{/if}
		</div>

		<div class="space-y-4">
			{#if wantVideo}
				<VideoUrlInput onValidEmbed={addVideoFromEmbed} />
			{/if}
			{#if wantImage}
				{#if store.document}
					<ImageUploader lessonId={store.document.id} onReady={addImageFromUpload} />
				{/if}
			{/if}
			{#if wantDiagram}
				{#if store.document}
					<DiagramUploader
						lessonId={store.document.id}
						onImageReady={addImageFromUpload}
						onSvgReady={(svg: string) => onSvgChange?.(svg)}
					/>
				{/if}
			{/if}
			{#if !wantVideo && !wantImage && !wantDiagram}
				<p class="text-xs text-slate-500">Choose an image or video block to use the media picker.</p>
			{/if}
		</div>

		<div>
			<p class="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Library</p>
			<MediaGrid
				mediaList={Object.values(docMedia)}
				selectedId={mediaId}
				filterType={wantVideo ? 'video' : wantImage || wantDiagram ? 'image' : undefined}
				onpick={pickMedia}
			/>
		</div>
	{/if}
</div>
