<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { page } from '$app/state';
	import { providePrintMode, type LessonDocument } from 'lectio';
	import { buildApiUrl } from '$lib/api/client';
	import LessonReadOnlyView from '$lib/builder/components/canvas/LessonReadOnlyView.svelte';
	import '$lib/builder/styles/print.css';
	import {
		forceEagerImages,
		waitForPrintImages,
		type PrintImageWaitResult
	} from '$lib/studio/print-readiness';

	const lessonId = $derived(page.params.id);
	const token = $derived(page.url.searchParams.get('token'));
	const audience = $derived(page.url.searchParams.get('audience') === 'student' ? 'student' : 'teacher');

	providePrintMode(() => page.url.searchParams.get('print') === 'true');

	let lessonDocument = $state<LessonDocument | null>(null);
	let dataReady = $state(false);
	let captureReady = $state(false);
	let fetchStatus = $state('not-started');
	let loadError = $state<string | null>(null);
	let imageDebug = $state<PrintImageWaitResult | null>(null);

	onMount(async () => {
		try {
			if (!lessonId) {
				loadError = 'Missing lesson id.';
				dataReady = true;
				captureReady = true;
				return;
			}

			fetchStatus = 'fetching';
			const endpoint = buildApiUrl(
				`/api/v1/builder/lessons/${encodeURIComponent(lessonId)}/print-document?audience=${encodeURIComponent(audience)}`
			);
			const headers: Record<string, string> = {};
			if (token) {
				headers.Authorization = `Bearer ${token}`;
			}

			const response = await fetch(endpoint, { headers });
			fetchStatus = `response-${response.status}`;
			if (!response.ok) {
				loadError = `Lesson unavailable for print (${response.status}).`;
				dataReady = true;
				captureReady = true;
				return;
			}

			lessonDocument = (await response.json()) as LessonDocument;
			dataReady = true;
			await tick();
			forceEagerImages();
			imageDebug = await waitForPrintImages({ timeoutMs: 10_000 });
			captureReady = true;
		} catch (error) {
			loadError = error instanceof Error ? error.message : 'Failed to load print view.';
			dataReady = true;
			captureReady = true;
		}
	});
</script>

<div
	data-generation-complete={captureReady ? 'true' : 'false'}
	data-print-route="builder-print-readable"
	data-fetch-status={fetchStatus}
	data-lesson-id={lessonId}
	data-audience={audience}
	data-image-count={imageDebug?.image_count ?? 0}
	data-images-loaded={imageDebug?.loaded_count ?? 0}
	data-images-failed={imageDebug?.failed_count ?? 0}
	data-images-timed-out={imageDebug?.timed_out ? 'true' : 'false'}
	data-failed-image-sources={imageDebug?.failed_sources?.length
		? JSON.stringify(imageDebug.failed_sources.slice(0, 12))
		: ''}
>
	{#if dataReady && loadError}
		<p class="print-error">{loadError}</p>
	{:else if dataReady && lessonDocument}
		<LessonReadOnlyView document={lessonDocument} />
	{/if}
</div>

<style>
	.print-error {
		padding: 1rem;
		font-size: 0.875rem;
		color: #b91c1c;
	}
</style>
