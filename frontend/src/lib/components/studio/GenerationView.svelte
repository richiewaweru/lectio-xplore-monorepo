<script lang="ts">
	import { onDestroy } from 'svelte';

	import {
		connectGenerationEvents,
		getGenerationDetail,
		getGenerationDocument
	} from '$lib/api/client';
	import { friendlyGenerationErrorMessage } from '$lib/generation/error-messages';
	import {
		applyGenerationStreamEvent,
		type GenerationStreamContext
	} from '$lib/generation/live-stream';
	import { buildSectionPreview } from '$lib/generation/preview';
	import {
		buildSectionSlots,
		normalizeDocument
	} from '$lib/generation/viewer-state';
	import { generationState, setGenerationBanner, setGenerationDocument } from '$lib/stores/studio';
	import { roleLabel } from '$lib/studio/presentation';
	import type {
		GenerationAccepted,
		GenerationDetail,
		GenerationDocument,
		PlanningGenerationSpec,
		ProgressUpdateEvent,
		RuntimePolicyEvent,
		RuntimeProgressEvent
	} from '$lib/types';

	interface Props {
		accepted: GenerationAccepted;
		onReset: () => void;
	}

	const MAX_RECONNECT_ATTEMPTS = 3;

	let { accepted, onReset }: Props = $props();

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
	let activeSectionId = $state<string | null>(null);
	let sectionSignals = $state<GenerationStreamContext['sectionSignals']>({});
	let reconnectAttempts = $state(0);
	let connectionToken = 0;
	let cancelStream: (() => void) | null = null;
	let reconnectTimer: number | null = null;
	let streamClosedTerminally = false;
	let streamErrorRecoveryAttempted = false;

	const generationId = $derived(accepted.generation_id);
	const sectionSlots = $derived(buildSectionSlots(document, plannedSections, sectionSignals));
	const failureMap = $derived(new Map((document?.failed_sections ?? []).map((entry) => [entry.section_id, entry])));
	const readySectionCount = $derived(
		sectionSlots.filter((slot) => slot.status === 'ready').length
	);
	const failedSectionCount = $derived(
		sectionSlots.filter((slot) => slot.status === 'failed').length
	);
	const isLive = $derived(detail?.status === 'pending' || detail?.status === 'running');
	const lessonFormat = $derived(resolveLessonFormat(detail?.planning_spec ?? null));
	const templateName = $derived(formatTemplateName(detail));
	const viewerTitle = $derived(document?.subject || detail?.subject || 'Live lesson');
	const showFullLesson = $derived(detail?.status === 'completed' || detail?.status === 'partial');
	const runtimeSectionsTotal = $derived(
		runtimeProgress?.sections_total ?? plannedSections ?? sectionSlots.length
	);
	const terminalSummary = $derived.by(() => {
		if (!detail) return null;
		if (detail.status === 'partial') {
			return detail.error ?? 'Some sections were generated, but the lesson did not fully finalize.';
		}
		if (detail.status === 'failed') {
			return detail.error ?? 'The generation failed before the lesson could be completed.';
		}
		return null;
	});

	function isStudioPlanningSpec(value: unknown): value is PlanningGenerationSpec {
		return Boolean(
			value &&
				typeof value === 'object' &&
				'source_brief' in value &&
				'template_decision' in value
		);
	}

	function resolveLessonFormat(spec: GenerationDetail['planning_spec']): string {
		if (isStudioPlanningSpec(spec)) {
			const format = spec.source_brief.signals.format;
			if (format === 'printed-booklet') return 'Printed booklet';
			if (format === 'screen-based') return 'Screen-based';
			if (format === 'both') return 'Print + screen';
		}
		return 'Live runtime';
	}

	function formatTemplateName(nextDetail: GenerationDetail | null): string {
		const templateId = nextDetail?.resolved_template_id ?? nextDetail?.requested_template_id ?? '';
		if (!templateId) {
			return 'Template loading';
		}
		return templateId
			.split('-')
			.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
			.join(' ');
	}

	function sectionRoleByPosition(position: number): string | null {
		const spec = detail?.planning_spec;
		if (!isStudioPlanningSpec(spec)) {
			return null;
		}
		const section = spec.sections.find((entry) => entry.order === position);
		return section ? roleLabel(section.role) : null;
	}

	function displaySectionStatus(slot: (typeof sectionSlots)[number]): (typeof slot)['status'] {
		return slot.status;
	}

	function activeProgressLabelForSection(sectionId: string): string | null {
		return progressUpdate?.section_id === sectionId ? progressUpdate.label : null;
	}

	function statusLabel(slot: (typeof sectionSlots)[number]): string {
		const status = displaySectionStatus(slot);
		if (status === 'ready') return 'Ready';
		if (status === 'failed') return 'Failed';
		if (status === 'planned') return 'Planned';
		if (status === 'generating') {
			return (
				slot.signal?.label ??
				activeProgressLabelForSection(slot.section_id) ??
				'Generating section...'
			);
		}
		if (status === 'partially_ready') {
			const pendingAssets = slot.partial?.pending_assets ?? [];
			if (slot.partial?.visual_mode === 'image') {
				return 'Generating media...';
			}
			if (pendingAssets.length > 0) {
				return 'Generating media...';
			}
			return slot.signal?.reason ?? 'Partially ready';
		}
		if (status === 'blocked_by_required_media') {
			return slot.signal?.reason ?? 'Blocked by required media';
		}
		return 'Planned';
	}

	function formatSeconds(seconds: number | null | undefined): string {
		if (seconds === null || seconds === undefined) return 'Pending';
		const rounded = Number.isInteger(seconds) ? seconds : Math.round(seconds);
		return `${rounded}s`;
	}

	function runtimeCounterLabel(
		running: number | null | undefined,
		queued: number | null | undefined
	): string {
		if (running === null || running === undefined || queued === null || queued === undefined) {
			return 'Pending';
		}
		return `${running} running / ${queued} queued`;
	}

	function sectionRuntimeLabel(): string {
		if (!runtimeProgress) {
			const total = plannedSections ?? sectionSlots.length;
			return total ? `${readySectionCount} complete / ${total} planned` : 'Pending';
		}
		return `${runtimeProgress.sections_completed} complete / ${runtimeProgress.sections_running} running / ${runtimeProgress.sections_queued} queued`;
	}

	function workerLabel(): string {
		if (!runtimePolicy) {
			return 'Pending';
		}
		return `${runtimePolicy.concurrency.max_section_concurrency} sections / ${runtimePolicy.concurrency.max_media_concurrency} media / ${runtimePolicy.concurrency.max_qc_concurrency} QC`;
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
				activeSectionId,
				sectionSignals
			},
			type,
			data
		);
		const prevDocument = document;
		document = result.next.document;
		plannedSections = result.next.plannedSections;
		qcSummary = result.next.qcSummary;
		progressUpdate = result.next.progressUpdate;
		runtimePolicy = result.next.runtimePolicy;
		runtimeProgress = result.next.runtimeProgress;
		viewerWarning = result.next.viewerWarning;
		activeSectionId = result.next.activeSectionId;
		sectionSignals = result.next.sectionSignals;
		if (document && document !== prevDocument) {
			syncDocument(document);
		}
		return { terminal: result.terminal };
	}

	function clearReconnectTimer() {
		if (reconnectTimer !== null) {
			window.clearTimeout(reconnectTimer);
			reconnectTimer = null;
		}
	}

	function closeStream(token?: number) {
		if (token !== undefined && token !== connectionToken) return;
		cancelStream?.();
		cancelStream = null;
	}

	function syncDocument(nextDocument: GenerationDocument) {
		const normalized = normalizeDocument(nextDocument);
		document = normalized;
		setGenerationDocument(normalized);
	}

	function applyGenerationSnapshot(nextDetail: GenerationDetail, nextDocument: GenerationDocument) {
		const normalizedDocument = normalizeDocument(nextDocument);
		const manifestCount = normalizedDocument.section_manifest.length;
		const sectionCount = normalizedDocument.sections.length;

		detail = nextDetail;
		document = normalizedDocument;
		setGenerationDocument(normalizedDocument);
		plannedSections =
			nextDetail.section_count ??
			(manifestCount > 0 ? manifestCount : sectionCount > 0 ? sectionCount : null);
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
		activeSectionId = null;
		clearReconnectTimer();
		setGenerationBanner(null);
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
		} catch {
			return false;
		}

		if (token !== connectionToken) return false;

		if (detail?.status === 'completed' || detail?.status === 'partial' || detail?.status === 'failed') {
			streamClosedTerminally = true;
			streamState = 'complete';
			activeSectionId = null;
			setGenerationBanner(null);
			closeStream(token);
			if (detail.status === 'failed') {
				error = friendlyGenerationErrorMessage(detail.error, detail.error_type, detail.error_code);
			}
			return true;
		}

		return false;
	}

	function scheduleReconnect(token: number, id: string) {
		if (token !== connectionToken) return;

		closeStream(token);
		clearReconnectTimer();

		if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
			streamState = 'complete';
			setGenerationBanner(
				'Connection lost. Generation may still complete in the background. Check the dashboard history if this lesson does not reopen.'
			);
			return;
		}

		reconnectAttempts += 1;
		streamState = 'reconnecting';
		const delayMs = 600 * 2 ** (reconnectAttempts - 1);
		setGenerationBanner(
			`Connection lost. Reconnecting to the live generation stream (attempt ${reconnectAttempts} of ${MAX_RECONNECT_ATTEMPTS})...`
		);

		reconnectTimer = window.setTimeout(async () => {
			try {
				await refresh(id);
				if (detail?.status === 'completed' || detail?.status === 'partial' || detail?.status === 'failed') {
					streamState = 'complete';
					setGenerationBanner(null);
					return;
				}
			} catch {
				// Keep the last known state visible and continue with reconnect.
			}

			connectStream(id);
		}, delayMs);
	}

	function connectStream(id: string) {
		clearReconnectTimer();
		closeStream();
		const myToken = ++connectionToken;
		streamClosedTerminally = false;
		streamErrorRecoveryAttempted = false;
		streamState = reconnectAttempts > 0 ? 'reconnecting' : 'connected';
		setGenerationBanner(reconnectAttempts > 0 ? 'Reconnecting to live generation...' : 'Live generation connected.');

		cancelStream = connectGenerationEvents(id, {
			onOpen() {
				if (myToken !== connectionToken) return;
				streamState = 'connected';
				if (reconnectAttempts > 0) {
					setGenerationBanner('Live generation reconnected.');
				} else {
					setGenerationBanner('Live generation connected.');
				}
				reconnectAttempts = 0;
			},
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
					setGenerationBanner(null);
					closeStream(myToken);
					return;
				}
				void revalidateTerminalState(myToken, id).then((handled) => {
					if (!handled) scheduleReconnect(myToken, id);
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
		activeSectionId = null;
		sectionSignals = {};
		reconnectAttempts = 0;
		streamClosedTerminally = false;
		streamErrorRecoveryAttempted = false;
		setGenerationBanner(null);
		clearReconnectTimer();
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
			clearReconnectTimer();
			closeStream();
			setGenerationBanner(null);
		};
	});

	onDestroy(() => {
		clearReconnectTimer();
		closeStream();
		setGenerationBanner(null);
	});
</script>

<section class="generation-shell">
	<header class="generation-header">
		<div>
			<p class="eyebrow">Generating</p>
			<h2>Generation stays inside the studio</h2>
			<p class="lede">
				Read ready sections while the remaining ones are still generating. Failures stay local to
				the section that hit trouble.
			</p>
		</div>
		<div class="header-actions">
			{#if showFullLesson}
				<a class="open-link" href={`/textbook/${generationId}`}>View full lesson -></a>
			{/if}
			<button class="secondary-button" type="button" onclick={onReset}>Create another lesson</button>
		</div>
	</header>

	{#if $generationState.connectionBanner}
		<div class="notice notice-info" role="status">
			<p>{$generationState.connectionBanner}</p>
			{#if streamState === 'complete' && !showFullLesson}
				<a href="/dashboard" class="dashboard-link">Open dashboard history</a>
			{/if}
		</div>
	{/if}

	{#if viewerWarning}
		<p class="notice notice-warn">{viewerWarning}</p>
	{/if}

	{#if error}
		<p class="notice notice-error">{error}</p>
	{/if}

	{#if terminalSummary}
		<div class={`notice ${detail?.status === 'failed' ? 'notice-error' : 'notice-warn'}`} role="status">
			<div class="terminal-summary">
				<p>{terminalSummary}</p>
				<details>
					<summary>Technical details</summary>
					<p>Status: {detail?.status}</p>
					<p>Quality passed: {detail?.quality_passed === null ? 'Unknown' : detail?.quality_passed ? 'Yes' : 'No'}</p>
					<p>Ready sections: {readySectionCount}</p>
					<p>Failed sections: {failedSectionCount}</p>
				</details>
			</div>
		</div>
	{/if}

	{#if loading}
		<div class="loading-panel" aria-busy="true">
			<div class="skeleton-sidebar"></div>
			<div class="skeleton-viewer"></div>
		</div>
	{:else}
		<div class="workspace">
			<aside class="progress-rail">
				<section class="rail-card">
					<p class="rail-label">Progress</p>
					<div class="progress-list">
						<div class="progress-row">
							<span class="progress-dot progress-dot-complete"></span>
							<div>
								<strong>Planning</strong>
								<p>Done</p>
							</div>
						</div>

						{#each sectionSlots as slot}
							<div class="progress-row">
								<span class={`progress-dot progress-dot-${displaySectionStatus(slot)}`}></span>
								<div>
									<strong>Section {slot.position}</strong>
									<p>{statusLabel(slot)}</p>
								</div>
							</div>
						{/each}
					</div>
				</section>

				<section class="rail-card">
					<p class="rail-label">Runtime</p>
					<div class="meta-list">
						<div>
							<span>Sections</span>
							<strong>{sectionRuntimeLabel()}</strong>
						</div>
						<div>
							<span>Media</span>
							<strong
								>{runtimeCounterLabel(
									runtimeProgress?.media_running,
									runtimeProgress?.media_queued
								)}</strong
							>
						</div>
						<div>
							<span>QC workers</span>
							<strong>{runtimeCounterLabel(runtimeProgress?.qc_running, runtimeProgress?.qc_queued)}</strong>
						</div>
						<div>
							<span>Retries</span>
							<strong
								>{runtimeCounterLabel(
									runtimeProgress?.retry_running,
									runtimeProgress?.retry_queued
								)}</strong
							>
						</div>
					</div>
				</section>

				<section class="rail-card">
					<p class="rail-label">Lesson</p>
					<div class="meta-list">
						<div>
							<span>Template</span>
							<strong>{templateName}</strong>
						</div>
						<div>
							<span>Sections</span>
							<strong>{runtimeSectionsTotal}</strong>
						</div>
						<div>
							<span>Format</span>
							<strong>{lessonFormat}</strong>
						</div>
						<div>
							<span>Workers</span>
							<strong>{workerLabel()}</strong>
						</div>
						<div>
							<span>Rerenders</span>
							<strong>{runtimePolicy ? `${runtimePolicy.max_section_rerenders} max` : 'Pending'}</strong>
						</div>
						<div>
							<span>Budget</span>
							<strong>{formatSeconds(runtimePolicy?.generation_timeout_seconds)}</strong>
						</div>
						<div>
							<span>Admission</span>
							<strong
								>{runtimePolicy
									? `${runtimePolicy.generation_max_concurrent_per_user} per user`
									: 'Pending'}</strong
							>
						</div>
						<div>
							<span>QC</span>
							<strong>{qcSummary ? `${qcSummary.passed} / ${qcSummary.total}` : 'Pending'}</strong>
						</div>
						<div>
							<span>Ready</span>
							<strong>{readySectionCount}</strong>
						</div>
						<div>
							<span>Failed</span>
							<strong>{failedSectionCount}</strong>
						</div>
					</div>
				</section>
			</aside>

			<section class="viewer">
				<div class="viewer-header">
					<div>
						<p class="viewer-label">Live workspace</p>
						<h3>{viewerTitle}</h3>
					</div>
					{#if isLive}
						<span class="live-badge">Live</span>
					{:else}
						<span class="complete-badge">
							{detail?.status === 'failed'
								? 'Failed'
								: detail?.status === 'partial'
									? 'Partially generated'
									: 'Complete'}
						</span>
					{/if}
				</div>

				<div class="viewer-sections">
					{#if sectionSlots.length}
						{#each sectionSlots as slot}
							{@const slotStatus = displaySectionStatus(slot)}
							{@const role = sectionRoleByPosition(slot.position)}
							{@const contentSection = slot.section ?? slot.partial?.content ?? null}
							<article class={`viewer-section viewer-section-${slotStatus}`}>
								<div class="viewer-section-label">
									Section {slot.position}{role ? ` - ${role}` : ''}
								</div>
								<h4>{slot.title}</h4>

								{#if slotStatus === 'ready' && slot.section}
									<p>{buildSectionPreview(slot.section)}</p>
								{:else if contentSection}
									<p>{buildSectionPreview(contentSection)}</p>
									<small>{statusLabel(slot)}</small>
								{:else if slotStatus === 'generating'}
									<div class="active-row">
										<span class="active-dot"></span>
										<p>{statusLabel(slot)}</p>
									</div>
								{:else if slotStatus === 'partially_ready'}
									<p>{statusLabel(slot)}</p>
								{:else if slotStatus === 'planned'}
									<p>{statusLabel(slot)}</p>
								{:else if slotStatus === 'failed'}
									<p>
										{failureMap.get(slot.section_id)?.error_summary ??
											'This section could not be generated.'}
									</p>
									{#if failureMap.get(slot.section_id)?.can_retry}
										<small>Retries are tracked in the run report while the rest of the lesson stays readable.</small>
									{/if}
								{:else if slotStatus === 'blocked_by_required_media'}
									<p>{statusLabel(slot)}</p>
								{:else}
									<p>{statusLabel(slot)}</p>
								{/if}
							</article>
						{/each}
					{:else}
						<article class="viewer-section viewer-section-planned">
							<div class="viewer-section-label">Section stream</div>
							<h4>Waiting for the first section</h4>
							<p>The generation worker has not published the first section yet.</p>
						</article>
					{/if}
				</div>
			</section>
		</div>
	{/if}
</section>

<style>
	.generation-shell {
		display: grid;
		gap: 1rem;
	}

	.generation-header,
	.header-actions,
	.viewer-header,
	.active-row {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: start;
	}

	.eyebrow,
	.rail-label,
	.viewer-label,
	.viewer-section-label {
		margin: 0;
		font-size: 0.76rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: #6b7c88;
	}

	h2,
	h3,
	h4,
	p {
		margin: 0;
	}

	.lede {
		max-width: 60ch;
		color: #625a50;
		line-height: 1.6;
	}

	.open-link,
	.secondary-button,
	.dashboard-link {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border-radius: 0.95rem;
		padding: 0.72rem 1.1rem;
		font: inherit;
		font-weight: 700;
		text-decoration: none;
	}

	.open-link {
		background: #1d9e75;
		color: #e1f5ee;
	}

	.secondary-button,
	.dashboard-link {
		border: none;
		background: #f1ece4;
		color: #4f5c65;
		cursor: pointer;
	}

	.notice,
	.loading-panel {
		border-radius: 1rem;
		padding: 0.95rem 1rem;
	}

	.notice-info {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: center;
		background: #eef8f4;
		color: #0b6a52;
	}

	.notice-warn {
		background: #fff8e4;
		color: #805d16;
	}

	.notice-error {
		background: #fff2ee;
		color: #7d3524;
	}

	.loading-panel,
	.workspace {
		display: grid;
		grid-template-columns: 220px minmax(0, 1fr);
		gap: 1rem;
	}

	.skeleton-sidebar,
	.skeleton-viewer {
		border-radius: 1.1rem;
		background: linear-gradient(90deg, #ece4d6, #f8f4ec, #ece4d6);
		background-size: 200% 100%;
		animation: shimmer 1.25s linear infinite;
	}

	.skeleton-sidebar {
		min-height: 18rem;
	}

	.skeleton-viewer {
		min-height: 24rem;
	}

	.progress-rail {
		display: grid;
		gap: 0.8rem;
		align-content: start;
	}

	.rail-card,
	.viewer {
		display: grid;
		gap: 0.9rem;
		border: 0.5px solid rgba(36, 52, 63, 0.12);
		border-radius: 1.25rem;
		background: #fffdf9;
		padding: 1rem;
	}

	.progress-list,
	.meta-list,
	.viewer-sections {
		display: grid;
		gap: 0.7rem;
	}

	.progress-row {
		display: flex;
		gap: 0.65rem;
		align-items: start;
	}

	.progress-row strong,
	.meta-list strong,
	.viewer h4 {
		color: #1d1b17;
	}

	.progress-row p,
	.meta-list span,
	.viewer-section p,
	.viewer-section small {
		color: #625a50;
		line-height: 1.55;
	}

	.progress-dot,
	.active-dot {
		flex-shrink: 0;
		border-radius: 999px;
	}

	.progress-dot {
		width: 0.65rem;
		height: 0.65rem;
		margin-top: 0.35rem;
		background: #c8beb0;
	}

	.progress-dot-complete,
	.progress-dot-ready {
		background: #1d9e75;
	}

	.progress-dot-generating {
		background: #1d9e75;
		animation: pulse 1.2s ease-in-out infinite;
	}

	.progress-dot-planned {
		background: #d6cdc1;
	}

	.progress-dot-partially_ready {
		background: #356582;
	}

	.progress-dot-failed {
		background: #c8822a;
	}

	.progress-dot-blocked_by_required_media {
		background: #8c8579;
	}

	.meta-list {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}

	.meta-list div {
		display: grid;
		gap: 0.2rem;
	}

	.viewer-header {
		align-items: center;
		border-bottom: 0.5px solid rgba(36, 52, 63, 0.08);
		padding-bottom: 0.9rem;
	}

	.live-badge,
	.complete-badge {
		display: inline-flex;
		align-items: center;
		border-radius: 999px;
		padding: 0.36rem 0.72rem;
		font-size: 0.78rem;
		font-weight: 700;
	}

	.live-badge {
		background: #e1f5ee;
		color: #085041;
	}

	.complete-badge {
		background: #f1ece4;
		color: #4f5c65;
	}

	.viewer-section {
		display: grid;
		gap: 0.4rem;
		border-radius: 1rem;
		padding: 0.95rem 1rem;
		border: 0.5px solid rgba(36, 52, 63, 0.08);
	}

	.viewer-section-ready {
		background: #fffdf9;
	}

	.viewer-section-generating {
		background: #eef8f4;
		border-color: rgba(29, 158, 117, 0.24);
	}

	.viewer-section-planned,
	.viewer-section-blocked_by_required_media {
		background: #f6f1e8;
		opacity: 0.72;
	}

	.viewer-section-partially_ready {
		background: #eef4f8;
		border-color: rgba(53, 101, 130, 0.24);
	}

	.viewer-section-failed {
		background: #fff5e8;
		border-color: rgba(186, 117, 23, 0.22);
	}

	.active-row {
		justify-content: flex-start;
		align-items: center;
	}

	.terminal-summary {
		display: grid;
		gap: 0.55rem;
	}

	.active-dot {
		width: 0.55rem;
		height: 0.55rem;
		background: #1d9e75;
		animation: pulse 1.2s ease-in-out infinite;
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.3;
		}
	}

	@keyframes shimmer {
		from {
			background-position: 200% 0;
		}
		to {
			background-position: -200% 0;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.progress-dot-generating,
		.active-dot,
		.skeleton-sidebar,
		.skeleton-viewer {
			animation: none;
		}
	}

	@media (max-width: 900px) {
		.loading-panel,
		.workspace {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 720px) {
		.generation-header,
		.header-actions,
		.notice-info,
		.viewer-header {
			flex-direction: column;
			align-items: stretch;
		}

		.header-actions > * {
			width: 100%;
		}
	}
</style>
