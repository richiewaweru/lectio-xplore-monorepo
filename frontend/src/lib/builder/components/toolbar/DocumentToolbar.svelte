<script lang="ts">
	import { onMount } from 'svelte';
	import type { LessonDocument } from 'lectio';
	import { connectivityStore } from '$lib/builder/stores/connectivity.svelte';
	import { getStorageEstimate } from '$lib/builder/utils/storage-estimate';
	import {
		estimatePageCount,
		pageWarningLevel,
		pageWarningMessage
	} from '$lib/builder/utils/page-estimate';
	import { downloadLessonDocument } from '$lib/builder/utils/file-io';
	import {
		checkBuilderLessonPrint,
		downloadBuilderLessonPdf,
		printDocument,
		type BuilderPdfAudience,
		type BuilderPrintPreflightResult
	} from '$lib/builder/utils/pdf-export';
	import { CloudOff, Eye, EyeOff, History, Printer, Share2, UploadCloud } from 'lucide-svelte';

	let {
		document,
		saveStatus = 'saved',
		onOpenMedia,
		onOpenHistory,
		onOpenShare,
		onSaveToDrive,
		lessonId,
		printPreviewActive = false,
		onTogglePrintPreview,
		onRetrySave
	}: {
		document: LessonDocument;
		saveStatus?: 'saved' | 'saving' | 'error';
		onOpenMedia?: () => void;
		onOpenHistory?: () => void;
		onOpenShare?: () => void;
		onSaveToDrive?: () => void;
		lessonId?: string;
		printPreviewActive?: boolean;
		onTogglePrintPreview?: () => void;
		onRetrySave?: () => void;
	} = $props();

	let storageAlmostFull = $state(false);
	let exportLoadingAudience = $state<BuilderPdfAudience | null>(null);
	let exportError = $state<string | null>(null);
	let printCheckLoading = $state(false);
	let printCheckError = $state<string | null>(null);
	let printCheckResult = $state<BuilderPrintPreflightResult | null>(null);
	let printCheckDocumentUpdatedAt = $state<string | null>(null);
	const blocks = $derived(document ? Object.values(document.blocks) : []);
	const heuristicPageCount = $derived(estimatePageCount(blocks));
	const printCheckStale = $derived(
		printCheckResult !== null && printCheckDocumentUpdatedAt !== document.updated_at
	);
	const pageCount = $derived(
		printCheckResult && !printCheckStale ? printCheckResult.page_count_estimate : heuristicPageCount
	);
	const warningLevel = $derived(pageWarningLevel(pageCount));
	const pageWarning = $derived(pageWarningMessage(pageCount));
	const printWarnings = $derived(printCheckResult?.warnings ?? []);

	async function refreshStorageHint(): Promise<void> {
		const est = await getStorageEstimate();
		storageAlmostFull = est != null && est.quota > 0 && est.used / est.quota >= 0.8;
	}

	function exportLesson(): void {
		downloadLessonDocument(document);
	}

	async function exportPdf(audience: BuilderPdfAudience): Promise<void> {
		if (!lessonId) return;
		exportLoadingAudience = audience;
		exportError = null;
		try {
			await downloadBuilderLessonPdf(lessonId, audience);
		} catch (error) {
			exportError = error instanceof Error ? error.message : 'Failed to export lesson PDF.';
		} finally {
			exportLoadingAudience = null;
		}
	}

	async function checkPrint(): Promise<void> {
		if (!lessonId) return;
		printCheckLoading = true;
		printCheckError = null;
		try {
			printCheckResult = await checkBuilderLessonPrint(lessonId, 'teacher');
			printCheckDocumentUpdatedAt = document.updated_at;
		} catch (error) {
			printCheckError = error instanceof Error ? error.message : 'Failed to check print layout.';
		} finally {
			printCheckLoading = false;
		}
	}

	onMount(() => {
		void refreshStorageHint();
		const id = setInterval(() => void refreshStorageHint(), 60_000);
		const doc = globalThis.document;
		const onVis = (): void => {
			if (doc.visibilityState === 'visible') {
				void refreshStorageHint();
			}
		};
		doc.addEventListener('visibilitychange', onVis);
		return () => {
			clearInterval(id);
			doc.removeEventListener('visibilitychange', onVis);
		};
	});
</script>

<header
	class="document-toolbar flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-6 py-3 shadow-sm"
	data-testid="document-toolbar"
>
	<div>
		<h1 class="text-lg font-semibold text-slate-900">{document.title}</h1>
		<p class="text-xs text-slate-500">{document.subject} - {document.preset_id}</p>
	</div>
	<div class="flex flex-wrap items-center gap-4">
		{#if !connectivityStore.online}
			<span class="inline-flex items-center gap-1 text-xs text-slate-500" title="Offline">
				<CloudOff size={14} aria-hidden="true" />
				<span class="hidden sm:inline">Offline</span>
			</span>
		{/if}
		{#if storageAlmostFull}
			<span class="max-w-xs text-xs text-amber-800" role="status">
				Storage almost full - export and remove old documents.
			</span>
		{/if}
		<span class="text-xs text-slate-500" aria-live="polite">
			{#if saveStatus === 'saving'}
				Saving...
			{:else if saveStatus === 'error'}
				<span class="font-medium text-red-600">Save failed</span>
			{:else}
				Saved
			{/if}
		</span>
		{#if saveStatus === 'error' && onRetrySave}
			<button
				type="button"
				class="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-100"
				data-testid="toolbar-retry-save"
				onclick={onRetrySave}
			>
				Retry save
			</button>
		{/if}
		<span
			class="text-xs tabular-nums"
			class:text-slate-500={warningLevel === 'none'}
			class:text-amber-600={warningLevel === 'info'}
			class:text-red-600={warningLevel === 'warn'}
			title={pageWarning ?? `~${pageCount} A4 pages`}
			data-testid="toolbar-page-count"
		>
			{printCheckResult && !printCheckStale ? '' : '~'}{pageCount} {pageCount === 1 ? 'page' : 'pages'}
		</span>
		<button
			type="button"
			class="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
			onclick={() => void checkPrint()}
			disabled={!lessonId || printCheckLoading}
			data-testid="toolbar-print-check"
		>
			<Printer size={16} aria-hidden="true" />
			{printCheckLoading ? 'Checking...' : 'Check print'}
		</button>
		{#if onOpenHistory}
			<button
				type="button"
				class="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
				data-testid="toolbar-history"
				onclick={onOpenHistory}
			>
				<History size={16} aria-hidden="true" />
				History
			</button>
		{/if}
		{#if onOpenShare}
			<button
				type="button"
				class="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
				data-testid="toolbar-share"
				onclick={onOpenShare}
			>
				<Share2 size={16} aria-hidden="true" />
				Share
			</button>
		{/if}
		{#if onSaveToDrive}
			<button
				type="button"
				class="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
				data-testid="toolbar-save-drive"
				onclick={onSaveToDrive}
			>
				<UploadCloud size={16} aria-hidden="true" />
				Save to Drive
			</button>
		{/if}
		{#if onOpenMedia}
			<button
				type="button"
				class="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
				onclick={onOpenMedia}
			>
				Media
			</button>
		{/if}
		{#if onTogglePrintPreview}
			<button
				type="button"
				class="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
				onclick={onTogglePrintPreview}
				data-testid="toolbar-print-preview"
			>
				{#if printPreviewActive}
					<EyeOff size={16} aria-hidden="true" />
					Exit preview
				{:else}
					<Eye size={16} aria-hidden="true" />
					Print preview
				{/if}
			</button>
		{/if}
		<button
			type="button"
			class="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
			onclick={() => printDocument()}
			data-testid="toolbar-print"
		>
			<Printer size={16} aria-hidden="true" />
			Print / PDF
		</button>
		<button
			type="button"
			class="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
			onclick={() => void exportPdf('teacher')}
			disabled={!lessonId || exportLoadingAudience !== null}
			data-testid="toolbar-export-teacher-pdf"
		>
			{exportLoadingAudience === 'teacher' ? 'Exporting teacher PDF...' : 'Teacher PDF'}
		</button>
		<button
			type="button"
			class="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
			onclick={() => void exportPdf('student')}
			disabled={!lessonId || exportLoadingAudience !== null}
			data-testid="toolbar-export-student-pdf"
		>
			{exportLoadingAudience === 'student' ? 'Exporting student PDF...' : 'Student PDF'}
		</button>
		<button
			type="button"
			class="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
			onclick={exportLesson}
		>
			Export
		</button>
		<a href="/" class="text-sm font-medium text-blue-600 hover:text-blue-800">All documents</a>
	</div>
	{#if exportError}
		<p class="w-full text-sm text-red-700" data-testid="toolbar-export-error">{exportError}</p>
	{/if}
	{#if printCheckError}
		<p class="w-full text-sm text-red-700" data-testid="toolbar-print-check-error">{printCheckError}</p>
	{/if}
	{#if printCheckResult}
		<div
			class="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700"
			class:opacity-60={printCheckStale}
			data-testid="toolbar-print-check-result"
		>
			<div class="flex flex-wrap items-center gap-3">
				<span class="font-medium text-slate-900">{printCheckResult.page_count_estimate} {printCheckResult.page_count_estimate === 1 ? 'page' : 'pages'}</span>
				<span>Images: {printCheckResult.images.loaded} loaded, {printCheckResult.images.failed} failed, {printCheckResult.images.timed_out} timed out</span>
				{#if printCheckStale}
					<span class="font-medium text-amber-700">Document changed</span>
				{/if}
			</div>
			{#if printWarnings.length}
				<ul class="mt-2 list-disc space-y-1 pl-5 text-amber-800">
					{#each printWarnings as warning}
						<li>{warning}</li>
					{/each}
				</ul>
			{:else}
				<p class="mt-2 text-emerald-700">No print warnings found.</p>
			{/if}
		</div>
	{/if}
</header>
