<script lang="ts">
	import { parseVideoUrl } from '$lib/builder/utils/media-utils';

	let {
		onValidEmbed
	}: {
		onValidEmbed: (embedUrl: string) => void;
	} = $props();

	let draft = $state('');
	let error = $state<string | null>(null);

	function apply(): void {
		const parsed = parseVideoUrl(draft);
		if (!parsed) {
			error = 'Use a YouTube or Vimeo link.';
			return;
		}
		error = null;
		onValidEmbed(parsed.embedUrl);
	}
</script>

<div class="space-y-2">
	<label class="block text-xs font-medium text-slate-600" for="video-url-input">Paste video URL</label>
	<div class="flex flex-wrap gap-2">
		<input
			id="video-url-input"
			type="url"
			class="min-w-[12rem] flex-1 rounded-md border border-slate-300 px-2 py-1.5 text-sm"
			placeholder="https://www.youtube.com/watch?v=… or Vimeo link"
			bind:value={draft}
		/>
		<button
			type="button"
			class="rounded-md bg-slate-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-900"
			onclick={apply}
		>
			Add video
		</button>
	</div>
	{#if error}
		<p class="text-xs text-amber-700">{error}</p>
	{/if}
	{#if draft && parseVideoUrl(draft)}
		<div class="aspect-video w-full max-w-md overflow-hidden rounded-md border border-slate-200 bg-black/5">
			<iframe
				class="h-full w-full"
				title="Video preview"
				src={parseVideoUrl(draft)!.embedUrl}
				allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
				allowfullscreen
			></iframe>
		</div>
	{/if}
</div>
