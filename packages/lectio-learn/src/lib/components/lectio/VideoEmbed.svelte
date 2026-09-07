<script lang="ts">
	import type { MediaReference } from '$lib/teacher/document';
	import type { VideoEmbedContent } from '$lib/schema/types';
	import { Card } from '$lib/components/ui/card';
	import { usePrintMode } from '$lib/utils/printContext';

	let {
		content,
		media = {}
	}: {
		content: VideoEmbedContent;
		media?: Record<string, MediaReference>;
	} = $props();

	const ref = $derived(content.media_id ? media[content.media_id] : undefined);
	const isVideo = $derived(ref?.type === 'video' && ref.url);

	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());

	function publicWatchUrl(embedUrl: string): string {
		const yt = embedUrl.match(/youtube\.com\/embed\/([^?&/]+)/);
		if (yt?.[1]) return `https://www.youtube.com/watch?v=${yt[1]}`;
		const vm = embedUrl.match(/player\.vimeo\.com\/video\/(\d+)/);
		if (vm?.[1]) return `https://vimeo.com/${vm[1]}`;
		return embedUrl;
	}

	function youtubeThumb(embedUrl: string): string | null {
		const m = embedUrl.match(/youtube\.com\/embed\/([^?&/]+)/);
		if (m?.[1]) return `https://img.youtube.com/vi/${m[1]}/hqdefault.jpg`;
		return null;
	}

	function iframeSrc(baseUrl: string): string {
		try {
			const u = new URL(baseUrl);
			if (content.start_time != null && content.start_time >= 0) {
				u.searchParams.set('start', String(Math.floor(content.start_time)));
			}
			if (content.end_time != null && content.end_time >= 0) {
				u.searchParams.set('end', String(Math.floor(content.end_time)));
			}
			return u.toString();
		} catch {
			return baseUrl;
		}
	}

	const resolvedSrc = $derived(isVideo && ref ? iframeSrc(ref.url) : '');
	const thumbUrl = $derived(isVideo && ref ? youtubeThumb(ref.url) : null);
	const qrTarget = $derived(isVideo && ref ? publicWatchUrl(ref.url) : '');

	let qrDataUrl = $state<string | null>(null);

	$effect(() => {
		if (typeof window === 'undefined' || content.print_fallback !== 'qr-link' || !qrTarget) {
			qrDataUrl = null;
			return;
		}
		let cancelled = false;
		void import('qrcode')
			.then((QR) => QR.default.toDataURL(qrTarget, { width: 140, margin: 1 }))
			.then((url) => {
				if (!cancelled) qrDataUrl = url;
			})
			.catch(() => {
				if (!cancelled) qrDataUrl = null;
			});
		return () => {
			cancelled = true;
		};
	});

	const printTitle = $derived(
		content.caption?.trim() || (isVideo && ref ? 'Embedded video' : 'Video')
	);
</script>

{#if printMode}
	<div class="video-embed-print rh-gap-component-tight" data-print-container="atomic">
		<p class="eyebrow">Video</p>
		{#if isVideo && ref}
			<p class="text-base font-semibold leading-snug">{printTitle}</p>
			<p class="text-sm leading-6">Watch online: {publicWatchUrl(ref.url)}</p>
		{:else}
			<p class="text-sm leading-6">Video is not available for this block in print.</p>
		{/if}
		<p class="text-xs leading-5 text-muted-foreground">Full playback is available in the digital version.</p>
	</div>
{:else}
<Card class="border-primary/10 bg-white/88 rh-pad-card">
	<div class="rh-gap-component-tight">
		<p class="eyebrow">Video</p>

		{#if isVideo && ref}
			<div class="print:hidden">
				<div class="aspect-video w-full overflow-hidden rounded-[1rem] border border-border/70 bg-black/5">
					<iframe
						class="h-full w-full"
						src={resolvedSrc}
						title={content.caption?.trim() || 'Embedded video'}
						allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
						allowfullscreen
						referrerpolicy="strict-origin-when-cross-origin"
					></iframe>
				</div>
			</div>

			{#if content.print_fallback === 'hide'}
				<div class="hidden print:block"></div>
			{:else if content.print_fallback === 'thumbnail'}
				<div class="hidden print:block">
					{#if thumbUrl}
						<img src={thumbUrl} alt="" class="max-h-48 w-auto rounded-md border border-border/60" />
					{:else}
						<p class="text-sm text-muted-foreground">Video (open the digital lesson to watch).</p>
					{/if}
					{#if content.caption?.trim()}
						<p class="mt-2 text-sm text-foreground/85">{content.caption}</p>
					{/if}
				</div>
			{:else if content.print_fallback === 'qr-link'}
				<div class="hidden print:flex print:flex-col print:items-start print:gap-2">
					{#if qrDataUrl}
						<img src={qrDataUrl} alt="QR code linking to video" class="h-36 w-36" />
					{:else}
						<p class="text-sm text-muted-foreground">Generating QR code…</p>
					{/if}
					<p class="break-all text-xs text-muted-foreground">{qrTarget}</p>
					{#if content.caption?.trim()}
						<p class="text-sm text-foreground/85">{content.caption}</p>
					{/if}
				</div>
			{/if}

			{#if content.caption?.trim()}
				<p class="print:hidden text-sm text-muted-foreground">{content.caption}</p>
			{/if}
		{:else}
			<p class="text-sm text-muted-foreground">Video is not available (add a video URL in the editor).</p>
		{/if}
	</div>
</Card>
{/if}
