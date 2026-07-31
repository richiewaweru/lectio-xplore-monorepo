<!--
	V3 PDF print route — Lectio renderer only.
	Diagnostics: ?debugPrint=true for adapter diagnostic overlay.
-->
<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { page } from '$app/state';
	import { providePrintMode } from 'lectio';
	import '$lib/styles/print.css';
	import { buildApiUrl } from '$lib/api/client';
	import V3LectioPrintDocumentView from '$lib/components/studio/V3LectioPrintDocumentView.svelte';
	import {
		adaptV3PackToLectioDocument,
		adaptV3PackToLectioDocumentWithDiagnostics,
		type V3PackAdapterDiagnostic,
		type V3PackDocument
	} from '$lib/studio/v3-pack-to-lectio-document';
	import { forceEagerImages, waitForPrintImages, type PrintImageWaitResult } from '$lib/studio/print-readiness';
	import type { GenerationDocument } from '$lib/types';

	const generationId = $derived(page.params.id);
	const token = $derived(page.url.searchParams.get('token'));
	const debugPrint = $derived(page.url.searchParams.get('debugPrint') === 'true');
	const includePackKey = $derived(page.url.searchParams.get('includePackKey') === 'true');
	const showPrintDiagnostics = $derived(debugPrint);

	providePrintMode(() => page.url.searchParams.get('print') === 'true');

	let dataReady = $state(false);
	let captureReady = $state(false);
	let fetchStatus = $state('not-started');
	let sectionCount = $state(0);
	let templateId = $state('none');
	let loadError = $state<string | null>(null);
	let lectioDocument = $state<GenerationDocument | null>(null);
	let adapterDiagnostic = $state<V3PackAdapterDiagnostic | null>(null);
	let subject = $state('');
	let imageDebug = $state<PrintImageWaitResult | null>(null);

	/** DOM `data-renderer` for Playwright: reflects the branch that actually rendered. */
	const dataRenderer = $derived.by(() => {
		if (!dataReady) return 'lectio';
		if (loadError) return 'lectio';
		if (lectioDocument) return 'lectio';
		return 'lectio-adapter-failed';
	});

	onMount(async () => {
		try {
			if (!generationId) {
				loadError = 'Missing generation id.';
				dataReady = true;
				captureReady = true;
				return;
			}

			fetchStatus = 'fetching';

			const endpoint = buildApiUrl(
				`/api/v1/v3/generations/${encodeURIComponent(generationId)}/document`
			);

			const headers: Record<string, string> = {};
			if (token) headers.Authorization = `Bearer ${token}`;

			const res = await fetch(endpoint, { headers });
			fetchStatus = `response-${res.status}`;

			if (!res.ok) {
				loadError = `Document unavailable for print (${res.status}).`;
				dataReady = true;
				captureReady = true;
				return;
			}

			const data = (await res.json()) as V3PackDocument;

			const list = Array.isArray(data.sections) ? data.sections : [];
			sectionCount = list.length;
			templateId = typeof data.template_id === 'string' ? data.template_id : 'missing';
			subject = typeof data.subject === 'string' ? data.subject.trim() : '';

			try {
				if (debugPrint) {
					const r = adaptV3PackToLectioDocumentWithDiagnostics(data, {
						routeGenerationId: generationId
					});
					lectioDocument = r.document;
					adapterDiagnostic = r.diagnostic;
				} else {
					lectioDocument = adaptV3PackToLectioDocument(data, {
						routeGenerationId: generationId,
						includeAnswerKey: includePackKey
					});
					adapterDiagnostic = null;
				}
			} catch (err) {
				console.error('[v3-print] adaptV3PackToLectioDocument failed', err);
				lectioDocument = null;
				adapterDiagnostic = null;
			}

			dataReady = true;
			await tick();
			forceEagerImages();
			imageDebug = await waitForPrintImages({ timeoutMs: 10_000 });
			captureReady = true;
		} catch (err) {
			loadError = err instanceof Error ? err.message : 'Failed to load print view.';
			dataReady = true;
			captureReady = true;
		}
	});
</script>

<svelte:head>
	<title>{subject ? `${subject} — print` : 'Lesson print'}</title>
</svelte:head>

<div
	data-generation-complete={captureReady ? 'true' : 'false'}
	data-print-route="studio-print-readable"
	data-renderer={dataRenderer}
	data-fetch-status={fetchStatus}
	data-section-count={sectionCount}
	data-template-id={templateId}
	data-generation-id={generationId}
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
	{:else if dataReady && !loadError}
		{#if showPrintDiagnostics}
			<div class="print-diagnostics">
				<p>
					<span class="print-diagnostics-label">Renderer:</span>
					{dataRenderer}
				</p>
				<p><span class="print-diagnostics-label">Fetch status:</span> {fetchStatus}</p>
				<p><span class="print-diagnostics-label">Section count:</span> {sectionCount}</p>
				<p><span class="print-diagnostics-label">Template ID:</span> {templateId}</p>
				<p><span class="print-diagnostics-label">Load error:</span> {loadError ?? 'none'}</p>
				<p>
					<span class="print-diagnostics-label">Images:</span>
					{imageDebug?.loaded_count ?? 0}/{imageDebug?.image_count ?? 0} loaded; failed
					{imageDebug?.failed_count ?? 0}; timed_out={imageDebug?.timed_out ?? false}
				</p>
				{#if debugPrint && adapterDiagnostic}
					<p>
						<span class="print-diagnostics-label">Adapter missing section_id:</span>
						{adapterDiagnostic.missing_section_ids}
					</p>
					<p>
						<span class="print-diagnostics-label">Adapter synthetic titles:</span>
						{adapterDiagnostic.normalized_header_count}
					</p>
					<details class="adapter-fields">
						<summary>Fields by section (debug)</summary>
						<ul>
							{#each adapterDiagnostic.fields_by_section as row}
								<li>{row.section_id}: {row.fields.join(', ')}</li>
							{/each}
						</ul>
					</details>
				{/if}
			</div>
		{/if}

		{#if lectioDocument}
			<V3LectioPrintDocumentView document={lectioDocument} />
		{:else}
			<p class="print-error">Unable to render print view.</p>
		{/if}
	{/if}
</div>

<style>
	.print-error {
		padding: 1rem;
		font-size: 0.875rem;
		color: #b91c1c;
	}

	.print-diagnostics {
		margin-bottom: 1rem;
		padding-bottom: 0.75rem;
		border-bottom: 1px solid #ccc;
		font-size: 0.75rem;
		line-height: 1.4;
		color: #333;
	}

	.print-diagnostics p {
		margin: 0.15rem 0;
	}

	.print-diagnostics-label {
		font-weight: 600;
		margin-right: 0.35rem;
	}

	.adapter-fields {
		margin-top: 0.35rem;
		font-size: 0.7rem;
	}

	.adapter-fields ul {
		margin: 0.25rem 0 0 1rem;
		padding: 0;
	}
</style>
