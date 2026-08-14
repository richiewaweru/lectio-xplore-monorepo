<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';

	import {
		downloadV3GenerationPdf,
		fetchV3Document,
		getV3GenerationDetail,
		retryNativeVisuals
	} from '$lib/api/v3';
	import { coerceV3DocumentToPack } from '$lib/studio/v3-document';
	import { extractLectioDocumentV2 } from '$lib/studio/document-version';
	import { getBookletExportPolicy, isBookletStatus } from '$lib/studio/v3-booklet';
	import V3BookletPackView from '$lib/components/studio/V3BookletPackView.svelte';
	import LectioPageDocumentView from '$lib/components/studio/LectioPageDocumentView.svelte';
	import type {
		BookletStatus,
		V3DraftPack,
		V3GenerationDetail,
		V3VisualQualityFlag,
		V3VisualQualitySummary
	} from '$lib/types/v3';
	import type { LectioDocument } from '@lectio/page/contract';

	const generationId = $derived(page.params.id ?? '');

	let loading = $state(true);
	let loadError = $state<string | null>(null);
	let detail = $state<V3GenerationDetail | null>(null);
	let pack = $state<V3DraftPack | null>(null);
	let pageDocumentV2 = $state<LectioDocument | null>(null);
	let pdfLoading = $state(false);
	let pdfError = $state<string | null>(null);
	let pdfOpen = $state(false);
	let schoolName = $state('');
	let teacherName = $state('');
	let exportDate = $state('');
	let includeAnswers = $state(true);
	let visualRetrying = $state(false);
	let visualRetryError = $state<string | null>(null);

	function flaggedVisuals(
		value: V3GenerationDetail['visual_quality']
	): V3VisualQualityFlag[] {
		if (!value) return [];
		if (Array.isArray(value)) {
			return value.filter(
				(entry): entry is V3VisualQualityFlag => Boolean(entry) && entry.status === 'flagged_quality'
			);
		}
		const summary = value as V3VisualQualitySummary;
		const entries = Array.isArray(summary.flagged) ? summary.flagged : [summary];
		return entries.filter((entry) => entry?.status === 'flagged_quality');
	}

	function visualRetryable(value: V3GenerationDetail['visual_quality']): boolean {
		if (!value) return false;
		if (Array.isArray(value)) return value.some((entry) => entry?.status === 'flagged_quality');
		const summary = value as V3VisualQualitySummary;
		return Boolean(
			summary.retryable &&
			((summary.flagged?.length ?? 0) > 0 || (summary.failed_request_ids?.length ?? 0) > 0)
		);
	}

	const nativeGenerationReady = $derived(
		pageDocumentV2 && (detail?.status === 'ready' || detail?.status === 'completed')
	);
	const nativeVisualRetryable = $derived(
		Boolean(detail?.native_whole_lesson || detail?.document_contract_version === 2) &&
		visualRetryable(detail?.visual_quality)
	);

	const resolvedStatus = $derived.by<BookletStatus>(() => {
		if (pageDocumentV2 && nativeGenerationReady && !nativeVisualRetryable) return 'final_ready';
		if (pageDocumentV2) return 'streaming_preview';
		if (pack?.status) return pack.status;
		if (detail && isBookletStatus(detail.booklet_status)) {
			return detail.booklet_status;
		}
		return 'streaming_preview';
	});
	const exportPolicy = $derived(getBookletExportPolicy(resolvedStatus));
	const flaggedVisualQuality = $derived(
		nativeVisualRetryable ? flaggedVisuals(detail?.visual_quality) : []
	);

	const supplementLineage = $derived.by(() => {
		const source = detail?.planning_artifact?.source;
		if (source?.kind === 'supplement' && source.parent_generation_id) {
			return source;
		}
		return null;
	});

	async function loadGeneration(id: string): Promise<void> {
		loading = true;
		loadError = null;
		visualRetryError = null;
		detail = null;
		pack = null;
		pageDocumentV2 = null;
		try {
			const [nextDetail, document] = await Promise.all([
				getV3GenerationDetail(id),
				fetchV3Document(id)
			]);
			detail = nextDetail;
			const v2 = extractLectioDocumentV2(document);
			if (v2) {
				pageDocumentV2 = v2;
				return;
			}
			if (nextDetail.native_whole_lesson || nextDetail.document_contract_version === 2) {
				throw new Error('Native document contract error: LectioDocumentV2 is missing or malformed.');
			}
			const nextPack = coerceV3DocumentToPack(id, document, {
				templateId: nextDetail.template_id,
				fallbackStatus: isBookletStatus(nextDetail.booklet_status)
					? nextDetail.booklet_status
					: 'draft_needs_review'
			});
			if (!nextPack) {
				throw new Error('Document is not renderable yet.');
			}
			pack = nextPack;
		} catch (err) {
			loadError = err instanceof Error ? err.message : 'Failed to load V3 generation.';
		} finally {
			loading = false;
		}
	}

	async function handleRetryFlaggedVisuals(): Promise<void> {
		if (!generationId || flaggedVisualQuality.length === 0 || visualRetrying) return;
		visualRetrying = true;
		visualRetryError = null;
		try {
			await retryNativeVisuals(generationId);
			await loadGeneration(generationId);
		} catch (err) {
			visualRetryError = err instanceof Error ? err.message : 'Could not retry flagged visuals.';
		} finally {
			visualRetrying = false;
		}
	}

	async function handleDownloadPdf() {
		if (!generationId) return;
		if (!exportPolicy.enabled) {
			pdfError = 'PDF export is unavailable for this booklet status.';
			return;
		}
		if (!schoolName.trim() || !teacherName.trim()) {
			pdfError = 'School name and teacher name are required.';
			return;
		}
		pdfLoading = true;
		pdfError = null;
		try {
			await downloadV3GenerationPdf(generationId, {
				school_name: schoolName.trim(),
				teacher_name: teacherName.trim(),
				date: exportDate.trim() || null,
				include_toc: false,
				include_answers: includeAnswers,
				edition: includeAnswers ? 'teacher' : 'student'
			});
			pdfOpen = false;
		} catch (err) {
			pdfError = err instanceof Error ? err.message : 'Failed to export PDF.';
		} finally {
			pdfLoading = false;
		}
	}

	onMount(() => {
		if (!generationId) {
			loading = false;
			loadError = 'Generation id is missing.';
			return;
		}
		void loadGeneration(generationId);
	});
</script>

<div class="mx-auto w-full max-w-5xl px-4 py-6">
	{#if loading}
		<p class="text-sm text-muted-foreground">Loading V3 generation...</p>
	{:else if loadError}
		<p class="text-sm text-destructive" role="alert">{loadError}</p>
	{:else if pageDocumentV2 || pack}
		<div class="mb-4 rounded-lg border border-border/60 bg-card p-4">
			{#if nativeVisualRetryable}
				<div
					class="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-300/70 bg-amber-50 px-3 py-2 text-sm text-amber-950"
					data-testid="visual-quality-warning"
				>
					<p>
						{flaggedVisualQuality.length === 1
							? 'One visual was flagged for quality review.'
							: flaggedVisualQuality.length > 1
								? `${flaggedVisualQuality.length} visuals were flagged for quality review.`
								: 'A required visual is still being processed.'}
						The lesson is not final yet. Retry visuals without rebuilding upstream work.
					</p>
					<button
						type="button"
						class="rounded-md border border-amber-700/50 px-3 py-1.5 text-sm font-medium hover:bg-amber-100 disabled:opacity-60"
						onclick={handleRetryFlaggedVisuals}
						disabled={visualRetrying}
					>
						{visualRetrying ? 'Retrying visuals...' : 'Retry visuals'}
					</button>
				</div>
			{/if}
			{#if visualRetryError}
				<p class="mb-3 text-sm text-destructive" role="alert">{visualRetryError}</p>
			{/if}
			<div class="flex flex-wrap items-center justify-between gap-3">
				<div>
					<p class="text-xs uppercase tracking-wide text-muted-foreground">
						{pageDocumentV2 ? 'V2 page document' : 'V3 generation'}
					</p>
					<h1 class="text-lg font-semibold">
						{pageDocumentV2?.title ?? detail?.title ?? detail?.subject ?? generationId}
					</h1>
					<p class="text-sm text-muted-foreground">
						{#if pageDocumentV2}
							Document version: 2 - Sections: {pageDocumentV2.sections.length}
						{:else if pack}
							Status: {pack.status} - Sections: {pack.sections.length}
						{/if}
					</p>
					{#if supplementLineage}
						<p class="mt-2 text-sm text-muted-foreground">
							Companion resource based on
							<a
								class="font-medium text-primary underline-offset-4 hover:underline"
								href={`/studio/generations/${supplementLineage.parent_generation_id}`}
							>
								parent lesson
							</a>
							{#if supplementLineage.target_resource_type}
								({supplementLineage.target_resource_type.replace(/_/g, ' ')})
							{/if}
						</p>
					{/if}
				</div>
				<button
					type="button"
					class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60"
					onclick={() => (pdfOpen = !pdfOpen)}
					disabled={!exportPolicy.enabled}
				>
					{exportPolicy.label}
				</button>
			</div>
			{#if pdfOpen}
				<div class="mt-3 rounded-lg border border-border/60 bg-background/50 p-4 space-y-3">
					<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
						<label class="flex flex-col gap-1 text-sm">
							School name
							<input
								bind:value={schoolName}
								placeholder="Springfield High"
								class="rounded-md border border-input bg-background px-3 py-1.5 text-sm"
							/>
						</label>
						<label class="flex flex-col gap-1 text-sm">
							Teacher name
							<input
								bind:value={teacherName}
								placeholder="Ms. Johnson"
								class="rounded-md border border-input bg-background px-3 py-1.5 text-sm"
							/>
						</label>
						<label class="flex flex-col gap-1 text-sm">
							Date (optional)
							<input
								bind:value={exportDate}
								type="date"
								class="rounded-md border border-input bg-background px-3 py-1.5 text-sm"
							/>
						</label>
					</div>
					<label class="flex items-center gap-2 text-sm">
						<input bind:checked={includeAnswers} type="checkbox" />
						Include answers
					</label>
					{#if pdfError}
						<p class="text-sm text-destructive" role="alert">{pdfError}</p>
					{/if}
					<button
						type="button"
						class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60"
						onclick={handleDownloadPdf}
						disabled={pdfLoading || !schoolName.trim() || !teacherName.trim()}
					>
						{pdfLoading ? 'Generating PDF...' : 'Download PDF'}
					</button>
				</div>
			{/if}
		</div>
		{#if pageDocumentV2}
			<LectioPageDocumentView document={pageDocumentV2} edition="teacher" />
		{:else if pack}
			<V3BookletPackView pack={pack} status={pack.status} issues={pack.booklet_issues} />
		{/if}
	{:else}
		<p class="text-sm text-muted-foreground">No renderable V3 booklet was found.</p>
	{/if}
</div>
