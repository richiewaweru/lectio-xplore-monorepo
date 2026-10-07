<script lang="ts">
import { getContext, onDestroy, onMount } from 'svelte';
	import LectioPageDocumentView from '$lib/print/components/studio/LectioPageDocumentView.svelte';
	import { extractLectioDocumentV2 } from '$lib/print/studio/document-version';
	import { downloadGenerationPdf } from '$lib/api/realizations';
	import { apiFetch } from '$lib/api/client';
	import { generatePrintRealization, getLessonIssues, retryLessonRealization } from '$lib/api/units';
	import type { LectioDocument } from '@lectio/page/contract';
	import type { LessonIssue, LessonIssueCounts, PathLesson, PreparedLessonStatus, Unit, UnitPath } from '$lib/types/units';
	import { Button, Dialog, InlineError, EmptyState, Tabs } from '$lib/ui';
	import LessonProgressPanel from '$lib/curriculum/lessons/LessonProgressPanel.svelte';
	import { autoRetryText } from '$lib/curriculum/lessons/lesson-progress';
	import { createSerializedPoll, LESSON_STATUS_POLL_MS, LESSON_STATUS_POLL_OPTIONS } from '$lib/curriculum/lessons/serialized-poll';
import { lessonArtifactUi, lessonWorkspaceHref, resolvePrintGenerationId, preparationIsApprovedAndFresh } from '$lib/curriculum/lessons/lesson-context';
import LessonIssuesPanel from '$lib/curriculum/lessons/LessonIssuesPanel.svelte';

	type Ctx = {
		unitId: string;
		lessonId: string;
		unit: Unit | null;
		path: UnitPath | null;
		lesson: PathLesson | null;
		preparation: PreparedLessonStatus | null;
		statusFresh: boolean;
		statusError: string | null;
		refreshPreparation: () => Promise<void>;
	};

	const ctx = getContext<Ctx>('lessonWorkspace');
	let activeTab = $state<'preview' | 'issues'>('preview');
	let generationId = $state<string | null>(null);
	let pageDocumentV2 = $state<LectioDocument | null>(null);
	let issues = $state<LessonIssue[]>([]);
	let issueCounts = $state<LessonIssueCounts | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);
	let busy = $state<string | null>(null);
	let exportOpen = $state(false);
	let schoolName = $state('');
	let teacherName = $state('');
	let includeAnswers = $state(true);
	let edition = $state<'teacher' | 'student'>('teacher');
	const artifact = $derived(lessonArtifactUi(ctx.preparation, 'print', error));

	function selectTab(id: string): void {
		if (id === 'preview' || id === 'issues') activeTab = id;
	}

	function printIsActive(): boolean {
		const state = ctx.preparation?.workspace?.print.state;
		return state === 'queued' || state === 'running';
	}

	// One serialized poller per page; stops on terminal states and on destroy.
	let pollFailures = 0;
	const printPoll = createSerializedPoll(async () => {
		try {
			await ctx.refreshPreparation();
			pollFailures = 0;
			generationId = resolvePrintGenerationId(ctx.preparation);
			if (generationId) {
				await loadDoc(generationId);
				error = null;
				return false;
			}
		} catch {
			// Tolerate a few transient failures, then stop instead of polling forever.
			if (++pollFailures >= 5) return false;
		}
		return printIsActive() && !pageDocumentV2;
	}, LESSON_STATUS_POLL_MS, LESSON_STATUS_POLL_OPTIONS);

	function stopPolling(): void {
		printPoll.stop();
	}

	function schedulePoll(): void {
		if (pageDocumentV2 || !printIsActive()) return;
		printPoll.start();
	}

	async function loadIssues(): Promise<void> {
		try {
			const response = await getLessonIssues(ctx.unitId, ctx.lessonId, 'print');
			issues = response.issues;
			issueCounts = response.counts;
		} catch (err) {
			issueCounts = null;
			issues = [{ id: 'issues-load-failed', path: 'print', severity: 'error', category: 'document', code: 'ISSUES_LOAD_FAILED', message: 'The issues for this lesson could not be loaded.', details: err instanceof Error ? err.message : 'Could not load Print issues.', repairable: false, source: 'workspace', group: 'blocking' }];
		}
	}

	async function loadDoc(gid: string) {
		const res = await apiFetch(`/api/v1/v3/generations/${encodeURIComponent(gid)}/document`);
		if (!res.ok) throw new Error(`Print document unavailable (${res.status}).`);
		const doc = extractLectioDocumentV2(await res.json());
		if (!doc) throw new Error('Print document is not ready yet.');
		pageDocumentV2 = doc;
	}

	async function resolve() {
		stopPolling();
		loading = true;
		error = null;
		pageDocumentV2 = null;
		try {
			await ctx.refreshPreparation();
			generationId = resolvePrintGenerationId(ctx.preparation);
			if (generationId) {
				try { await loadDoc(generationId); }
				catch (err) { error = err instanceof Error ? err.message : 'Print document is unavailable.'; }
			}
			await loadIssues();
			if (!pageDocumentV2 && printIsActive()) {
				schedulePoll();
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load Print.';
		} finally {
			loading = false;
		}
	}

	async function createPrint() {
		if (!ctx.path || !ctx.lesson || artifact.exists || !ctx.statusFresh || !preparationIsApprovedAndFresh(ctx.preparation)) return;
		busy = 'create';
		error = null;
		try {
			await generatePrintRealization(ctx.unitId, ctx.path, ctx.lesson);
			await resolve();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not create Print.';
		} finally { busy = null; }
	}

	async function retryPrint() {
		if (!ctx.statusFresh || !ctx.path || !ctx.lesson || !artifact.realizationId || !(artifact.retryable || artifact.regenerable)) return;
		busy = 'retry';
		try {
			await retryLessonRealization(ctx.unitId, ctx.path, ctx.lesson, artifact.realizationId);
			await resolve();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not retry Print.';
		} finally { busy = null; }
	}

	async function exportPdf() {
		if (!generationId) return;
		busy = 'pdf';
		try {
			await downloadGenerationPdf(generationId, { school_name: schoolName.trim() || 'School', teacher_name: teacherName.trim(), include_toc: false, include_answers: includeAnswers, edition });
			exportOpen = false;
		} catch (err) { error = err instanceof Error ? err.message : 'Could not download PDF.'; }
		finally { busy = null; }
	}

	onMount(() => void resolve());
	onDestroy(stopPolling);
</script>

<div class="print-ws">
	<header class="bar">
		<Tabs
			active={activeTab}
			tabs={[
				{ id: 'preview', label: 'Preview' },
				{ id: 'edit', label: 'Edit', href: generationId ? `/studio/print/${encodeURIComponent(generationId)}` : undefined },
				{ id: 'issues', label: 'Issues' }
			]}
			onSelect={selectTab}
		/>
		{#if generationId && pageDocumentV2}<Button size="sm" onclick={() => (exportOpen = true)}>Download PDF</Button>{/if}
	</header>
	{#if error && artifact.state !== 'needs_attention' && artifact.state !== 'failed'}<InlineError message={error} hint={artifact.retryable ? 'You can retry or return to the plan.' : 'Refresh to check progress or return to the plan.'} />{/if}
	{#if ctx.statusError}<InlineError message={`Lesson status is stale: ${ctx.statusError}`} hint="Refresh the lesson workspace before creating or retrying Print." />{/if}
	{#if loading}
		<p class="muted">Loading Print…</p>
	{:else if activeTab === 'issues'}
		<LessonIssuesPanel {issues} counts={issueCounts} unitId={ctx.unitId} lessonId={ctx.lessonId} path="print" editBaseHref={generationId && pageDocumentV2 ? `/studio/print/${encodeURIComponent(generationId)}` : null} onRetry={retryPrint} allowRetry={ctx.statusFresh && (artifact.retryable || artifact.regenerable)} />
	{:else if artifact.state === 'not_created'}
		<EmptyState title="Print not created" description="Create a printable booklet from the approved teaching plan.">{#snippet actions()}<Button disabled={!ctx.statusFresh || !preparationIsApprovedAndFresh(ctx.preparation)} busy={busy === 'create'} onclick={() => void createPrint()}>{busy === 'create' ? 'Creating…' : 'Create Print'}</Button><a class="link" href={lessonWorkspaceHref(ctx.unitId, ctx.lessonId, 'plan')}>Review plan</a>{/snippet}</EmptyState>
	{:else if artifact.state === 'preparing'}
		<LessonProgressPanel progress={ctx.preparation?.workspace?.print.progress ?? null} fallbackTitle="Print is being created" />
	{:else if artifact.state === 'needs_review'}
		<EmptyState title="This lesson needs a teacher review before Print can be built" description="Quality checks flagged content in the prepared lesson document. Review and correct it before Print can continue.">
			{#snippet actions()}<a class="link" href={`/units/${encodeURIComponent(ctx.unitId)}/lessons/${encodeURIComponent(ctx.lessonId)}/review`}>Review flagged content</a><a class="link" href={lessonWorkspaceHref(ctx.unitId, ctx.lessonId, 'plan')}>Review plan</a>{/snippet}
		</EmptyState>
	{:else if activeTab === 'preview'}
		{#if pageDocumentV2}<div class="doc"><LectioPageDocumentView document={pageDocumentV2} edition="teacher" /></div>{:else}<EmptyState title="Print needs attention" description={artifact.recoveryAction === 'reprepare' ? 'This Print output is stale. Reprepare and review the lesson before creating another output.' : [artifact.errorSummary || error || 'The Print document is unavailable.', autoRetryText(artifact.autoRetry)].filter(Boolean).join(' ')}>{#snippet actions()}{#if ctx.statusFresh && artifact.retryable}<Button variant="secondary" busy={busy === 'retry'} onclick={() => void retryPrint()}>Retry Print</Button>{/if}{#if ctx.statusFresh && artifact.regenerable && !artifact.retryable}<Button variant="secondary" busy={busy === 'retry'} onclick={() => void retryPrint()}>Regenerate Print</Button>{/if}<a class="link" href={lessonWorkspaceHref(ctx.unitId, ctx.lessonId, 'plan')}>Review plan</a>{/snippet}</EmptyState>{/if}
	{/if}
</div>

<Dialog bind:open={exportOpen} title="Download PDF" description="Choose edition and optional branding.">
	<label class="field"><span>Edition</span><select bind:value={edition}><option value="teacher">Teacher edition</option><option value="student">Student edition</option></select></label>
	<label class="field"><span>School name</span><input bind:value={schoolName} placeholder="Optional" /></label>
	<label class="field"><span>Teacher name</span><input bind:value={teacherName} placeholder="Optional" /></label>
	<label class="check"><input type="checkbox" bind:checked={includeAnswers} /> Include answers</label>
	{#snippet footer()}<Button variant="secondary" onclick={() => (exportOpen = false)}>Cancel</Button><Button busy={busy === 'pdf'} onclick={() => void exportPdf()}>{busy === 'pdf' ? 'Preparing…' : 'Download PDF'}</Button>{/snippet}
</Dialog>

<style>
	.print-ws { display: grid; gap: var(--space-3); }
	.bar, .link { display: flex; align-items: center; gap: var(--space-3); }
	.bar { justify-content: space-between; align-items: flex-start; flex-wrap: wrap; }
	.bar :global(.tabs) { flex: 1; margin-bottom: 0; }
	.doc { background: var(--surface); border: 1px solid var(--rule); border-radius: var(--radius-lg); padding: var(--space-4); overflow: auto; }
	.muted { color: var(--ink-2); }
	.link { color: var(--accent); font-size: 0.875rem; font-weight: 550; text-decoration: none; }
	.field { display: grid; gap: 0.4rem; margin-bottom: var(--space-3); font-size: 0.8125rem; font-weight: 600; color: var(--ink-2); }
	input, select { font: inherit; font-weight: 400; padding: 0.55rem 0.7rem; border-radius: var(--radius-md); border: 1px solid var(--rule); background: var(--surface); color: var(--ink); }
	.check { display: flex; align-items: center; gap: 0.5rem; font-size: 0.875rem; color: var(--ink); }
</style>
