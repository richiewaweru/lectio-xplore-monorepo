<script lang="ts">
	import { uploadLessonMedia } from '$lib/builder/api/media-upload';
	import { validateRasterImageFile } from '$lib/builder/utils/media-utils';

	let {
		lessonId,
		onReady
	}: {
		lessonId: string;
		onReady: (payload: { url: string; filename: string; mimeType: string }) => void;
	} = $props();

	let warning = $state<string | null>(null);
	let uploading = $state(false);

	async function onPick(e: Event): Promise<void> {
		const input = e.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		input.value = '';
		if (!file) return;
		const v = validateRasterImageFile(file);
		if (!v.ok) {
			warning = v.reason;
			return;
		}
		warning = null;
		try {
			uploading = true;
			const uploaded = await uploadLessonMedia(lessonId, file);
			onReady({
				url: uploaded.url,
				filename: uploaded.filename ?? file.name,
				mimeType: uploaded.mime_type
			});
		} catch (error) {
			warning = error instanceof Error ? error.message : 'Upload failed.';
		} finally {
			uploading = false;
		}
	}
</script>

<div class="space-y-2">
	<label class="block text-xs font-medium text-slate-600" for="image-upload-input">Upload image</label>
	<input
		id="image-upload-input"
		type="file"
		accept="image/png,image/jpeg,image/webp,image/gif"
		class="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border file:border-slate-300 file:bg-white file:px-3 file:py-1.5 file:text-sm file:font-medium"
		disabled={uploading}
		onchange={onPick}
	/>
	{#if uploading}
		<p class="text-xs text-slate-500">Uploading image...</p>
	{/if}
	{#if warning}
		<p class="text-xs text-amber-700">{warning}</p>
	{/if}
</div>
