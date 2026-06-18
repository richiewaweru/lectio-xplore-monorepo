<script lang="ts">
	import { page } from '$app/state';
	import { providePrintMode } from 'lectio';
	import '$lib/styles/print.css';
	import LectioDocumentView from '$lib/components/LectioDocumentView.svelte';
	import {
		applyGenerationStreamEvent,
		type GenerationStreamContext
	} from '$lib/generation/live-stream';
	import {
		buildSectionSlots,
		normalizeDocument
	} from '$lib/generation/viewer-state';
	import {
		connectGenerationEvents,
		downloadGenerationPdf,
		getGenerationDetail,
		getGenerationDocument
	} from '$lib/api/client';
	import { downloadLessonDocument, exportToLessonDocument } from '$lib/generation/export-document';
	import { friendlyGenerationErrorMessage } from '$lib/generation/error-messages';
	import type { PDFExportRequest } from '$lib/types';
	import type {
		GenerationDetail,
		GenerationDocument,
		ProgressUpdateEvent,
		RuntimePolicyEvent,
		RuntimeProgressEvent
	} from '$lib/types';

	const generationId = $derived(page.params.id);
	const isPrintMode = $derived(page.url.searchParams.get('print') === 'true');
	providePrintMode(() => isPrintMode);

	let detail = $state<GenerationDetail | null>(null);
	let document = $state<GenerationDocument | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let streamState = $state<'idle' | 'connected' | 'reconnecting' | 'complete'>('idle');
	let plannedSections = $state<number | null>(null);
	let qcSummary = $state<{ passed: number; total: number } | null>(null);
	let progressUpdate = $state<ProgressUpdateEvent | null>(null);
	let runtimePolicy = $state<RuntimePolicyEvent | null>(null);
	let runtimeProgress = $state<RuntimeProgressEvent['snapshot'] | null>(null);
	let viewerWarning = $state<string | null>(null);
	let sectionSignals = $state<GenerationStreamContext['sectionSignals']>({});
	let exportPdfOpen = $state(false);
	let exportPdfLoading = $state(false);
	let exportPdfError = $state<string | null>(null);
	let schoolName = $state('');
	let teacherName = $state('');
	let exportDate = $state('');
	let includeToc = $state(true);
	let includeAnswers = $state(true);
	let exportPreset = $state<'teacher' | 'student'>('teacher');
	let connectionToken = 0;
	let cancelStream: (() => void) | null = null;
	let streamClosedTerminally = false;
	let streamErrorRecoveryAttempted = false;
	const sectionSlots = $derived(buildSectionSlots(document, plannedSections, sectionSignals));
	const readySectionCount = $derived(
		sectionSlots.filter((slot) => slot.status === 'ready').length
	);
	const failedSectionCount = $derived(
		sectionSlots.filter((slot) => slot.status === 'failed').length
	);
	const streamLabel = $derived(
		detail?.status === 'completed'
			? detail.quality_passed === false
				? 'completed with QC issues'
				: 'complete'
			: detail?.status === 'partial'
				? 'partially generated'
			: detail?.status === 'failed'
				? 'failed'
				: progressUpdate?.label ?? streamState
	);
	const progressStageLabel = $derived(
		progressUpdate?.stage ? progressUpdate.stage.replaceAll('_', ' ') : null
	);
	const sectionTitleMap = $derived(buildSectionTitleMap(document));
	const weakSections = $derived(buildWeakSectionSummaries(document, sectionTitleMap));
	const canExportPdf = $derived(detail?.status === 'completed' && !!document && !isPrintMode);
	const printReady = $derived(
		!!document &&
			!loading &&
			detail?.status === 'completed' &&
			(sectionSlots.length === 0 || sectionSlots.every((slot) => slot.status === 'ready'))
	);

	function formatSeconds(seconds: number | null | undefined): string {
		if (seconds === null || seconds === undefined) return 'Pending';
		const rounded = Number.isInteger(seconds) ? seconds : Math.round(seconds);
		return `${rounded}s`;
	}

	function runningQueuedLabel(running: number | null | undefined, queued: number | null | undefined): string {
		if (running === null || running === undefined || queued === null || queued === undefined) {
			return 'Pending';
		}
		return `${running} running / ${queued} queued`;
	}

	function closeStream(token?: number) {
		if (token !== undefined && token !== connectionToken) return;
		cancelStream?.();
		cancelStream = null;
	}

	function applyStreamResult(
		type: string,
		data: string
	): { terminal: { kind: 'complete' | 'generation_failed' | 'error'; message?: string | null } | null } {
		const result = applyGenerationStreamEvent(
			{
				document,
				plannedSections,
				qcSummary,
				progressUpdate,
				runtimePolicy,
				runtimeProgress,
				viewerWarning,
				activeSectionId: null,
				sectionSignals
			},
			type,
			data
		);
		document = result.next.document ? normalizeDocument(result.next.document) : result.next.document;
		plannedSections = result.next.plannedSections;
		qcSummary = result.next.qcSummary;
		progressUpdate = result.next.progressUpdate;
		runtimePolicy = result.next.runtimePolicy;
		runtimeProgress = result.next.runtimeProgress;
		viewerWarning = result.next.viewerWarning;
		sectionSignals = result.next.sectionSignals;
		return { terminal: result.terminal };
	}

	async function handlePdfExport() {
		if (!generationId) return;
		exportPdfLoading = true;
		exportPdfError = null;
		try {
			const request: PDFExportRequest = {
				school_name: schoolName.trim(),
				teacher_name: teacherName.trim(),
				include_toc: includeToc,
				include_answers: includeAnswers
			};
			if (exportDate.trim()) {
				request.date = exportDate.trim();
			}
			if (!request.school_name || !request.teacher_name) {
				throw new Error('School name and teacher name are required.');
			}
			await downloadGenerationPdf(generationId, request);
			exportPdfOpen = false;
		} catch (err) {
			exportPdfError = err instanceof Error ? err.message : 'Failed to export PDF.';
		} finally {
			exportPdfLoading = false;
		}
	}

	function applyExportPreset(preset: 'teacher' | 'student') {
		exportPreset = preset;
		includeToc = true;
		includeAnswers = preset === 'teacher';
	}

	function buildSectionTitleMap(nextDocument: GenerationDocument | null): Map<string, string> {
		const map = new Map<string, string>();
		if (!nextDocument) {
			return map;
		}

		for (const item of nextDocument.section_manifest) {
			map.set(item.section_id, item.title);
		}
		for (const section of nextDocument.sections) {
			map.set(section.section_id, section.header?.title ?? `Section ${map.size + 1}`);
		}
		for (const failed of nextDocument.failed_sections) {
			map.set(failed.section_id, failed.title);
		}

		return map;
	}

	function buildWeakSectionSummaries(
		nextDocument: GenerationDocument | null,
		titleMap: Map<string, string>
	): Array<{
		section_id: string;
		title: string;
		warning: string;
		issues: GenerationDocument['qc_reports'][number]['issues'];
	}> {
		if (!nextDocument) {
			return [];
		}

		const failedIds = new Set(nextDocument.failed_sections.map((entry) => entry.section_id));

		return nextDocument.qc_reports
			.filter((report) => !failedIds.has(report.section_id))
			.filter((report) => !report.passed || report.warnings.length > 0)
			.map((report) => ({
				section_id: report.section_id,
				title: titleMap.get(report.section_id) ?? report.section_id,
				warning:
					report.warnings[0] ??
					report.issues[0]?.message ??
					'This section may benefit from another pass.',
				issues: report.issues
			}));
	}

	function applyGenerationSnapshot(nextDetail: GenerationDetail, nextDocument: GenerationDocument) {
		const normalizedDocument = normalizeDocument(nextDocument);
		const manifestCount = normalizedDocument.section_manifest.length;
		const sectionCount = normalizedDocument.sections.length;
		detail = nextDetail;
		document = normalizedDocument;
		plannedSections =
			nextDetail.section_count ?? (manifestCount > 0 ? manifestCount : sectionCount > 0 ? sectionCount : null);
		qcSummary = normalizedDocument.qc_reports.length
			? {
					passed: normalizedDocument.qc_reports.filter((report) => report.passed).length,
					total: normalizedDocument.qc_reports.length
				}
			: null;
	}

	async function refresh(id: string) {
		const [nextDetail, nextDocument] = await Promise.all([
			getGenerationDetail(id),
			getGenerationDocument(id)
		]);
		applyGenerationSnapshot(nextDetail, nextDocument);
	}

	async function finalizeStream(token: number, id: string, nextError: string | null = null) {
		if (token !== connectionToken) return;
		streamClosedTerminally = true;
		streamState = 'complete';
		closeStream(token);
		await refresh(id);
		if (detail?.status === 'failed') {
			error = friendlyGenerationErrorMessage(detail.error, detail.error_type, detail.error_code);
			return;
		}
		if (nextError) {
			error = nextError;
		}
	}

	async function revalidateTerminalState(token: number, id: string): Promise<boolean> {
		if (token !== connectionToken || streamErrorRecoveryAttempted) return false;
		streamErrorRecoveryAttempted = true;
		try {
			await refresh(id);
		} catch (err) {
			console.error('[Lectio] Stream recovery refresh failed:', err);
			return false;
		}
		if (token !== connectionToken) return false;
		if (detail?.status === 'completed' || detail?.status === 'partial' || detail?.status === 'failed') {
			streamClosedTerminally = true;
			streamState = 'complete';
			closeStream(token);
			if (detail.status === 'failed') {
				error = friendlyGenerationErrorMessage(detail.error, detail.error_type, detail.error_code);
			}
			return true;
		}
		return false;
	}

	function connectStream(id: string) {
		closeStream();
		const myToken = ++connectionToken;
		streamClosedTerminally = false;
		streamErrorRecoveryAttempted = false;
		streamState = 'connected';

		cancelStream = connectGenerationEvents(id, {
			onEvent(type, data) {
				if (myToken !== connectionToken) return;
				const { terminal } = applyStreamResult(type, data);
				if (terminal?.kind === 'complete') {
					void finalizeStream(myToken, id);
				} else if (terminal?.kind === 'generation_failed' || terminal?.kind === 'error') {
					void finalizeStream(myToken, id, terminal.message ?? null);
				}
			},
			onError(err) {
				if (myToken !== connectionToken) return;
				if (
					streamClosedTerminally ||
					detail?.status === 'completed' ||
					detail?.status === 'partial' ||
					detail?.status === 'failed'
				) {
					streamState = 'complete';
					closeStream(myToken);
					return;
				}
				void revalidateTerminalState(myToken, id).then((handled) => {
					if (!handled) streamState = 'reconnecting';
				});
			}
		});
	}

	async function loadGeneration(id: string) {
		loading = true;
		error = null;
		qcSummary = null;
		plannedSections = null;
		progressUpdate = null;
		runtimePolicy = null;
		runtimeProgress = null;
		viewerWarning = null;
		sectionSignals = {};
		streamClosedTerminally = false;
		streamErrorRecoveryAttempted = false;
		closeStream();

		try {
			await refresh(id);

			if (detail?.status === 'failed') {
				error = friendlyGenerationErrorMessage(detail.error, detail.error_type, detail.error_code);
				streamState = 'complete';
				return;
			}

			if (detail?.status === 'pending' || detail?.status === 'running') {
				connectStream(id);
			} else {
				streamState = 'complete';
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load generation.';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		if (!generationId) {
			return;
		}
		void loadGeneration(generationId);
		return () => {
			closeStream();
		};
	});
</script>

<div
	class="page-shell"
	data-generation-complete={printReady ? 'true' : 'false'}
	data-print-mode={isPrintMode ? 'true' : 'false'}
>
	{#if !isPrintMode}
		<div class="header">
			<div>
				<p class="eyebrow">Generation</p>
				<h1>{detail?.subject ?? generationId}</h1>
				{#if detail}
					<div class="meta">
						<span class="status status-{detail.status}">{detail.status}</span>
						<span>{detail.resolved_template_id ?? detail.requested_template_id}</span>
						<span>{detail.resolved_preset_id ?? detail.requested_preset_id}</span>
					</div>
				{/if}
			</div>
			{#if canExportPdf}
				<div class="export-controls">
					<button type="button" class="pdf-btn" onclick={() => (exportPdfOpen = !exportPdfOpen)}>
						{exportPdfOpen ? 'Close PDF Export' : 'Export PDF'}
					</button>
				</div>
			{/if}
		</div>

		{#if exportPdfOpen}
			<section class="status-panel export-controls">
				<h2>Export PDF</h2>
				<div class="export-grid">
					<label>
						<span>School name</span>
						<input bind:value={schoolName} placeholder="Springfield High" />
					</label>
					<label>
						<span>Teacher name</span>
						<input bind:value={teacherName} placeholder="Ms. Johnson" />
					</label>
					<label>
						<span>Date</span>
						<input bind:value={exportDate} type="date" />
					</label>
				</div>
				<div class="preset-row">
					<p class="preset-label">Export preset</p>
					<div class="preset-buttons">
						<button
							type="button"
							class:active-preset={exportPreset === 'teacher'}
							class="preset-btn"
							onclick={() => applyExportPreset('teacher')}
						>
							Teacher copy
						</button>
						<button
							type="button"
							class:active-preset={exportPreset === 'student'}
							class="preset-btn"
							onclick={() => applyExportPreset('student')}
						>
							Student copy
						</button>
					</div>
				</div>
				<div class="export-toggles">
					<label><input bind:checked={includeToc} type="checkbox" /> Include table of contents</label>
					<label><input bind:checked={includeAnswers} type="checkbox" /> Include answers</label>
				</div>
				<div class="export-actions">
					<button type="button" class="pdf-btn" disabled={exportPdfLoading} onclick={handlePdfExport}>
						{exportPdfLoading ? 'Generating PDF...' : 'Download PDF'}
					</button>
					{#if exportPdfError}
						<p class="export-error">{exportPdfError}</p>
					{/if}
				</div>
			</section>
		{/if}

		{#if plannedSections !== null}
			<div class="status-panel">
				<p>
					Sections ready: {readySectionCount} / {plannedSections}
				</p>
				{#if failedSectionCount > 0}
					<p>Failed sections: {failedSectionCount}</p>
				{/if}
				<p>Stream: {streamLabel}</p>
				{#if progressUpdate && detail?.status !== 'completed' && detail?.status !== 'failed'}
					<p>Progress: {progressUpdate.label}</p>
					<p>Stage: {progressStageLabel}</p>
				{/if}
				{#if runtimeProgress}
					<p>
						Runtime sections: {runtimeProgress.sections_completed} complete / {runtimeProgress.sections_running}
						running / {runtimeProgress.sections_queued} queued
					</p>
					<p>
						Media workers: {runningQueuedLabel(
							runtimeProgress.media_running,
							runtimeProgress.media_queued
						)}
					</p>
					<p>
						QC workers: {runningQueuedLabel(runtimeProgress.qc_running, runtimeProgress.qc_queued)}
					</p>
					<p>
						Retries: {runningQueuedLabel(runtimeProgress.retry_running, runtimeProgress.retry_queued)}
					</p>
				{/if}
				{#if runtimePolicy}
					<p>
						Policy: {runtimePolicy.concurrency.max_section_concurrency} section / {runtimePolicy.concurrency.max_media_concurrency}
						media / {runtimePolicy.concurrency.max_qc_concurrency} QC workers
					</p>
					<p>
						Budget: {formatSeconds(runtimePolicy.generation_timeout_seconds)} total, rerenders {runtimePolicy.max_section_rerenders} max
					</p>
					<p>
						Admission: {runtimePolicy.generation_max_concurrent_per_user} concurrent generations per user
					</p>
				{/if}
				{#if qcSummary}
					<p>QC: {qcSummary.passed} / {qcSummary.total} passing</p>
				{/if}
			</div>
		{/if}

		{#if viewerWarning}
			<div class="warning"><strong>Viewer warning:</strong> {viewerWarning}</div>
		{/if}

		{#if document?.failed_sections?.length}
			<section class="failed-sections">
				<h2>Sections Not Completed</h2>
				<ul>
					{#each document.failed_sections as failed}
						<li>
							<div class="section-summary">
								<strong>{failed.title}</strong>
								<span>Failed at {failed.failed_at_node}: {failed.error_summary}</span>
							</div>
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		{#if weakSections.length}
			<section class="weak-sections">
				<h2>Sections Needing Another Pass</h2>
				<ul>
					{#each weakSections as weak}
						<li>
							<div class="section-summary">
								<strong>{weak.title}</strong>
								<span>{weak.warning}</span>
							</div>
						</li>
					{/each}
				</ul>
			</section>
		{/if}
	{/if}

	{#if error}
		<div class="error"><strong>Error:</strong> {error}</div>
	{:else if loading}
		<p>Loading generation...</p>
	{:else if document}
		<LectioDocumentView
			{document}
			sectionSlots={sectionSlots}
			onExportForBuilder={() => {
				const currentDocument = document;
				if (!currentDocument) return;
				const lesson = exportToLessonDocument(currentDocument);
				downloadLessonDocument(lesson);
			}}
		/>
	{:else}
		<p>No document is available yet.</p>
	{/if}
</div>

<style>
	.page-shell {
		display: grid;
		gap: var(--rh-gap-component, 1rem);
	}

	.header {
		display: flex;
		justify-content: space-between;
		gap: var(--rh-gap-component, 1rem);
		align-items: start;
	}

	.eyebrow {
		margin: 0 0 0.3rem 0;
		font-size: var(--rh-eyebrow-size, 0.78rem);
		letter-spacing: var(--rh-eyebrow-tracking, 0.14em);
		text-transform: uppercase;
		color: #6b7c88;
	}

	h1 {
		margin: 0;
		font-size: 1.6rem;
	}

	.meta {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2, 0.55rem);
		margin-top: var(--space-2, 0.5rem);
		color: #5d554a;
	}

	.status {
		padding: var(--space-1, 0.2rem) var(--space-2, 0.55rem);
		border-radius: 999px;
		font-size: 0.76rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.status-pending,
	.status-running {
		background: rgba(54, 101, 130, 0.12);
		color: #28516b;
	}

	.status-completed {
		background: rgba(61, 120, 73, 0.13);
		color: #276135;
	}

	.status-partial {
		background: rgba(194, 142, 43, 0.14);
		color: #8a6415;
	}

	.status-failed {
		background: rgba(148, 66, 46, 0.12);
		color: #8d3a26;
	}

	.status-panel,
	.failed-sections,
	.weak-sections,
	.warning,
	.error,
	.export-controls {
		padding: var(--rh-pad-card-tight, 1rem);
		border-radius: var(--rh-radius-card, 18px);
		background: rgba(255, 251, 244, 0.84);
		border: 1px solid rgba(36, 52, 63, 0.1);
	}

	.export-grid {
		display: grid;
		gap: var(--rh-gap-component-tight, 0.75rem);
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		margin-top: var(--space-3, 0.75rem);
	}

	.export-grid label,
	.export-toggles label {
		display: grid;
		gap: var(--space-1, 0.35rem);
	}

	.export-grid input {
		border: 1px solid rgba(36, 52, 63, 0.18);
		border-radius: var(--rh-radius-inner, 10px);
		padding: var(--space-2, 0.6rem) var(--space-3, 0.75rem);
		font: inherit;
		background: rgba(255, 255, 255, 0.82);
	}

	.export-toggles {
		display: flex;
		flex-wrap: wrap;
		gap: var(--rh-gap-component, 1rem);
		margin-top: var(--space-4, 0.9rem);
	}

	.preset-row {
		display: grid;
		gap: var(--space-2, 0.55rem);
		margin-top: var(--space-4, 1rem);
	}

	.preset-label {
		margin: 0;
		font-size: 0.82rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: #5f574d;
	}

	.preset-buttons {
		display: flex;
		flex-wrap: wrap;
		gap: var(--rh-gap-component-tight, 0.75rem);
	}

	.preset-btn {
		border: 1px solid rgba(31, 43, 52, 0.18);
		background: rgba(255, 255, 255, 0.8);
		color: #24343f;
		border-radius: 999px;
		padding: var(--space-2, 0.55rem) var(--space-4, 0.95rem);
		font-weight: 600;
		cursor: pointer;
	}

	.active-preset {
		background: #24343f;
		color: #fffaf2;
	}

	.export-actions {
		display: grid;
		gap: var(--space-2, 0.6rem);
		margin-top: var(--space-4, 1rem);
	}

	.pdf-btn {
		border: 1px solid rgba(31, 43, 52, 0.18);
		background: #24343f;
		color: #fffaf2;
		border-radius: 999px;
		padding: var(--space-3, 0.65rem) var(--space-4, 1rem);
		font-weight: 600;
		cursor: pointer;
	}

	.pdf-btn:disabled {
		opacity: 0.65;
		cursor: progress;
	}

	.export-error {
		margin: 0;
		color: #8d3a26;
	}

	.error {
		border-color: rgba(148, 66, 46, 0.18);
		background: rgba(255, 242, 238, 0.9);
		color: #7d3524;
	}

	.warning {
		border-color: rgba(169, 129, 37, 0.18);
		background: rgba(255, 248, 225, 0.92);
		color: #7f5d13;
	}

	.failed-sections ul {
		margin: var(--space-3, 0.75rem) 0 0 0;
		padding-left: 1.1rem;
		display: grid;
		gap: var(--space-2, 0.55rem);
	}

	.failed-sections li {
		display: grid;
		gap: var(--space-1, 0.2rem);
	}

	.section-summary {
		display: grid;
		gap: var(--space-1, 0.15rem);
	}

</style>
