<script lang="ts">
	import type { MediaReference } from 'lectio';
	import type { DocumentStore } from '$lib/builder/stores/document.svelte';
	import ImageUploader from './ImageUploader.svelte';
	import VideoUrlInput from './VideoUrlInput.svelte';

	let {
		store,
		onclose
	}: {
		store: DocumentStore;
		onclose: () => void;
	} = $props();

	const items = $derived(
		store.document ? (Object.values(store.document.media) as MediaReference[]) : []
	);

	let editingAltId = $state<string | null>(null);
	let altDraft = $state('');

	function usageCount(id: string): number {
		return store.getMediaUsage(id).length;
	}

	function startAlt(m: MediaReference): void {
		editingAltId = m.id;
		altDraft = m.alt_text ?? '';
	}

	function saveAlt(): void {
		if (!editingAltId) return;
		store.updateMedia(editingAltId, { alt_text: altDraft });
		editingAltId = null;
	}

	function tryDelete(id: string): void {
		const n = usageCount(id);
		if (n > 0) {
			alert(`Used by ${n} blocks — remove from blocks first.`);
			return;
		}
		try {
			store.removeMedia(id);
		} catch (e) {
			alert(e instanceof Error ? e.message : String(e));
		}
	}

	function replaceImage(id: string, payload: { url: string; filename: string; mimeType: string }): void {
		store.updateMedia(id, {
			url: payload.url,
			filename: payload.filename,
			mime_type: payload.mimeType,
			type: 'image'
		});
	}

	function replaceVideo(id: string, embedUrl: string): void {
		store.updateMedia(id, { url: embedUrl, type: 'video' });
	}
</script>

<div
	class="media-manager-overlay fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4"
	role="dialog"
	aria-modal="true"
	aria-labelledby="media-manager-title"
	tabindex="-1"
	onclick={(e) => e.target === e.currentTarget && onclose()}
	onkeydown={(e) => e.key === 'Escape' && onclose()}
>
	<div class="mt-8 w-full max-w-3xl rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
		<div class="mb-4 flex items-center justify-between gap-2">
			<h2 id="media-manager-title" class="text-lg font-semibold text-slate-900">Media</h2>
			<button
				type="button"
				class="rounded-md px-2 py-1 text-sm text-slate-600 hover:bg-slate-100"
				onclick={onclose}
			>
				Close
			</button>
		</div>

		{#if items.length === 0}
			<p class="text-sm text-slate-500">No media in this lesson yet. Add images or videos from a block editor.</p>
		{:else}
			<ul class="space-y-4">
				{#each items as m (m.id)}
					<li class="rounded-lg border border-slate-200 p-4">
						<div class="flex flex-wrap gap-4">
							<div class="h-24 w-40 shrink-0 overflow-hidden rounded bg-slate-100">
								{#if m.type === 'image'}
									<img src={m.url} alt="" class="h-full w-full object-contain" />
								{:else}
									<div class="flex h-full items-center justify-center text-xs text-slate-500">Video</div>
								{/if}
							</div>
							<div class="min-w-0 flex-1 space-y-2">
								<p class="truncate text-sm font-medium text-slate-800">{m.filename ?? m.url.slice(0, 48)}</p>
								<p class="text-xs text-slate-500">Used by {usageCount(m.id)} block(s)</p>
								{#if editingAltId === m.id}
									<div class="flex flex-wrap items-end gap-2">
										<label class="block flex-1 min-w-[12rem]">
											<span class="text-xs font-medium text-slate-600">Alt text</span>
											<input
												class="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-sm"
												bind:value={altDraft}
											/>
										</label>
										<button
											type="button"
											class="rounded bg-slate-800 px-2 py-1 text-xs text-white"
											onclick={saveAlt}
										>
											Save
										</button>
										<button
											type="button"
											class="rounded border border-slate-300 px-2 py-1 text-xs"
											onclick={() => (editingAltId = null)}
										>
											Cancel
										</button>
									</div>
								{:else}
									<button
										type="button"
										class="text-xs font-medium text-blue-600 hover:text-blue-800"
										onclick={() => startAlt(m)}
									>
										Edit alt text
									</button>
								{/if}
								<div class="flex flex-wrap gap-2 border-t border-slate-100 pt-2">
									{#if m.type === 'image'}
										<div class="w-full max-w-xs">
											<p class="mb-1 text-xs text-slate-500">Replace image</p>
											{#if store.document}
												<ImageUploader
													lessonId={store.document.id}
													onReady={(p) => {
														replaceImage(m.id, p);
													}}
												/>
											{/if}
										</div>
									{:else if m.type === 'video'}
										<div class="w-full max-w-md">
											<p class="mb-1 text-xs text-slate-500">Replace video URL</p>
											<VideoUrlInput onValidEmbed={(url) => replaceVideo(m.id, url)} />
										</div>
									{/if}
									<button
										type="button"
										class="ml-auto rounded border border-red-200 px-2 py-1 text-xs text-red-700 hover:bg-red-50"
										onclick={() => tryDelete(m.id)}
									>
										Delete
									</button>
								</div>
							</div>
						</div>
					</li>
				{/each}
			</ul>
		{/if}
	</div>
</div>
