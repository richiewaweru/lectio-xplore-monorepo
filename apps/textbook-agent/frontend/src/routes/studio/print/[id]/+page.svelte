<script lang="ts">
	/**
	 * V3 PDF print route — @lectio/page LectioDocument only.
	 * Diagnostics: ?debugPrint=true for adapter diagnostic overlay.
	 */
	import { onMount, tick } from 'svelte';
	import { page } from '$app/state';
	import '$lib/print/styles/print.css';
	import { apiFetch } from '$lib/api/client';
	import LectioPageDocumentView from '$lib/print/components/studio/LectioPageDocumentView.svelte';
	import { extractLectioDocumentV2 } from '$lib/print/studio/document-version';
	import { forceEagerImages, waitForPrintImages, type PrintImageWaitResult } from '$lib/print/studio/print-readiness';
	import type { V3GenerationDetail } from '$lib/types/v3';
	import type { LectioDocument } from '@lectio/page/contract';
	import type { V3PackDocument } from '$lib/print/studio/v3-pack-to-lectio-document';

	const generationId = $derived(page.params.id);
	const token = $derived(page.url.searchParams.get('token'));
	const edition = $derived(
		page.url.searchParams.get('edition') === 'student' ? 'student' : 'teacher'
	);
	const debugPrint = $derived(page.url.searchParams.get('debugPrint') === 'true');
	const showPrintDiagnostics = $derived(debugPrint);

	function hasRetryableVisualQuality(value: unknown): boolean {
		if (Array.isArray(value)) return value.length > 0;
		if (!value || typeof value !== 'object') return false;
		const summary = value as Record<string, unknown>;
		return (
			summary.retryable === true ||
			(typeof summary.flagged_count === 'number' && summary.flagged_count > 0) ||
			(Array.isArray(summary.flagged) && summary.flagged.length > 0) ||
			(Array.isArray(summary.failed_request_ids) && summary.failed_request_ids.length > 0)
		);
	}

	async function fetchNativeGenerationDetail(
		id: string,
		headers: Record<string, string>
	): Promise<V3GenerationDetail> {
		const detailRes = await apiFetch(
			`/api/v1/v3/generations/${encodeURIComponent(id)}`,
			{ headers }
		);
		if (!detailRes.ok) {
			throw new Error(`Generation detail unavailable for print (${detailRes.status}).`);
		}
		return (await detailRes.json()) as V3GenerationDetail;
	}

	let dataReady = $state(false);
	let captureReady = $state(false);
	let fetchStatus = $state('not-started');
	let sectionCount = $state(0);
	let templateId = $state('none');
	let loadError = $state<string | null>(null);
	let pageDocumentV2 = $state<LectioDocument | null>(null);
	let subject = $state('');
	let imageDebug = $state<PrintImageWaitResult | null>(null);

	const dataRenderer = $derived.by(() => {
		if (!dataReady) return 'lectio-page-v2';
		if (loadError) return 'lectio-page-v2';
		if (pageDocumentV2) return 'lectio-page-v2';
		return 'lectio-page-missing';
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

			const headers: Record<string, string> = {};
			if (token) headers.Authorization = `Bearer ${token}`;

			const res = await apiFetch(
				`/api/v1/v3/generations/${encodeURIComponent(generationId)}/document`,
				{ headers }
			);
			fetchStatus = `response-${res.status}`;

			if (!res.ok) {
				loadError = `Document unavailable for print (${res.status}).`;
				dataReady = true;
				captureReady = true;
				return;
			}

			const data = (await res.json()) as V3PackDocument;
			const v2 = extractLectioDocumentV2(data);
			if (v2) {
				const detail = await fetchNativeGenerationDetail(generationId, headers);
				const native = detail.native_whole_lesson === true || detail.document_contract_version === 2;
				const nativeVisualsReady = detail.status === 'ready' || detail.status === 'completed';
				if (native && (!nativeVisualsReady || hasRetryableVisualQuality(detail.visual_quality))) {
					loadError = 'Native visuals are not ready for print. Retry visuals from Studio before exporting.';
					dataReady = true;
					captureReady = true;
					return;
				}
				pageDocumentV2 = v2;
				sectionCount = v2.sections.length;
				templateId = 'lectio-page-v2';
				subject = typeof v2.subject === 'string' ? v2.subject.trim() : v2.title;
			} else {
				const root = data as unknown as Record<string, unknown>;
				const nested = root.lectio_document as Record<string, unknown> | undefined;
				const nativeEnvelope =
					root.document_version === 2 || nested?.document_version === 2;
				if (nativeEnvelope) {
					loadError = 'Native document contract error: LectioDocumentV2 is missing or malformed.';
				} else {
					loadError =
						'Print requires a LectioDocument v2 payload. Legacy SectionContent packs are no longer rendered.';
				}
				sectionCount = Array.isArray(data.sections) ? data.sections.length : 0;
				templateId = typeof data.template_id === 'string' ? data.template_id : 'missing';
				subject = typeof data.subject === 'string' ? data.subject.trim() : '';
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
	{:else if dataReady && !loadError && pageDocumentV2}
		{#if showPrintDiagnostics}
			<div class="print-diagnostics">
				<p>
					<span class="print-diagnostics-label">Renderer:</span>
					{dataRenderer}
				</p>
				<p><span class="print-diagnostics-label">Fetch status:</span> {fetchStatus}</p>
				<p><span class="print-diagnostics-label">Section count:</span> {sectionCount}</p>
				<p><span class="print-diagnostics-label">Template ID:</span> {templateId}</p>
			</div>
		{/if}
		<LectioPageDocumentView document={pageDocumentV2} {edition} />
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
</style>
