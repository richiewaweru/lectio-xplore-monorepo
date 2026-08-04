<script lang="ts">
	import { uploadLessonMedia } from '$lib/builder/api/media-upload';
	import { sanitizeSvg, validateDiagramFile } from '$lib/builder/utils/media-utils';

	let {
		lessonId,
		onImageReady,
		onSvgReady
	}: {
		lessonId: string;
		onImageReady: (payload: { url: string; filename: string; mimeType: string }) => void;
		onSvgReady: (svgContent: string) => void;
	} = $props();

	let warning = $state<string | null>(null);
	let uploading = $state(false);
	let uploadLabel = $state('Upload image or SVG');

	async function onPick(e: Event): Promise<void> {
		const input = e.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		input.value = '';
		if (!file) return;

		const validation = validateDiagramFile(file);
		if (!validation.ok) {
			warning = validation.reason;
			return;
		}
		warning = null;

		if (validation.kind === 'svg') {
			try {
				uploading = true;
				uploadLabel = 'Reading SVG...';
				const text = await file.text();
				const clean = sanitizeSvg(text);
				if (!clean.trim()) {
					warning = 'SVG appears empty or contained only unsafe content.';
					return;
				}
				onSvgReady(clean);
			} catch {
				warning = 'Could not read SVG file.';
			} finally {
				uploading = false;
				uploadLabel = 'Upload image or SVG';
			}
			return;
		}

		try {
			uploading = true;
			uploadLabel = 'Uploading...';
			const uploaded = await uploadLessonMedia(lessonId, file);
			onImageReady({
				url: uploaded.url,
				filename: uploaded.filename ?? file.name,
				mimeType: uploaded.mime_type
			});
		} catch (error) {
			warning = error instanceof Error ? error.message : 'Upload failed.';
		} finally {
			uploading = false;
			uploadLabel = 'Upload image or SVG';
		}
	}
</script>

<div class="space-y-2">
	<label class="block text-xs font-medium text-slate-600" for="diagram-upload-input">{uploadLabel}</label>
	<input
		id="diagram-upload-input"
		type="file"
		accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml,.svg"
		class="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border file:border-slate-300 file:bg-white file:px-3 file:py-1.5 file:text-sm file:font-medium file:hover:bg-slate-50 file:cursor-pointer"
		disabled={uploading}
		onchange={onPick}
	/>
	<p class="text-xs text-slate-400">PNG, JPEG, WebP, GIF, or SVG. Max 10 MB for images, 2 MB for SVG.</p>
	{#if uploading}
		<p class="text-xs text-slate-500">Working...</p>
	{/if}
	{#if warning}
		<p class="text-xs text-amber-700">{warning}</p>
	{/if}
</div>
