<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import LectioPageDocumentView from '$lib/print/components/studio/LectioPageDocumentView.svelte';
	import PrintDocumentEditor from '$lib/print/components/studio/PrintDocumentEditor.svelte';
	import { extractLectioDocumentV2 } from '$lib/print/studio/document-version';
	import { downloadV3GenerationPdf } from '$lib/api/v3';
	import { apiFetch } from '$lib/api/client';
	import { generatePrintRealization, getLessonIssues, retryLessonRealization } from '$lib/api/units';
	import type { LectioDocument } from '@lectio/page/contract';
	import type { LessonIssue, PathLesson, PreparedLessonStatus, Unit, UnitPath } from '$lib/types/units';
	import { Button, Dialog, InlineError, EmptyState, Tabs } from '$lib/ui';
	import { lessonArtifactUi, lessonWorkspaceHref, resolvePrintGenerationId } from '$lib/curriculum/lessons/lesson-context';
	import LessonIssuesPanel from '$lib/curriculum/lessons/LessonIssuesPanel.svelte';

	type Ctx = {
		unitId: string;
		lessonId: string;
		unit: Unit | null;
		path: UnitPath | null;
		lesson: PathLesson | null;
		preparation: PreparedLessonStatus | null;
		refreshPreparation: () => Promise<void>;
	};

	const ctx = getContext<Ctx>('lessonWorkspace');
	let tab = $state<'preview' | 'edit' | 'issues'>('preview');
	let generationId = $state<string | null>(null);
	let pageDocumentV2 = $state<LectioDocument | null>(null);
	let issues = $state<LessonIssue[]>([]);
	let error = $state<string | null>(null);
	let loading = $state(true);
	let busy = $state<string | null>(null);
	let exportOpen = $state(false);
	let schoolName = $state('');
	let teacherName = $state('');
	let includeAnswers = $state(true);
	let edition = $state<'teacher' | 'student'>('teacher');
	const artifact = $derived(lessonArtifactUi(ctx.preparation, 'print', error));

	async function loadIssues(): Promise<void> {
		try {
			issues = (await getLessonIssues(ctx.unitId, ctx.lessonId, 'print')).issues;
		} catch (err) {
			issues = [{ id: 'issues-load-failed', path: 'print', severity: 'error', category: 'document', code: 'ISSUES_LOAD_FAILED', message: err instanceof Error ? err.message : 'Could not load Print issues.', repairable: false, source: 'workspace' }];
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
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load Print.';
		} finally {
			loading = false;
		}
	}

	async function createPrint() {
		if (!ctx.path || !ctx.lesson || artifact.exists) return;
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
		if (!ctx.path || !ctx.lesson || !artifact.realizationId) return;
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
			await downloadV3GenerationPdf(generationId, { school_name: schoolName.trim() || 'School', teacher_name: teacherName.trim(), include_toc: false, include_answers: includeAnswers, edition });
			exportOpen = false;
		} catch (err) { error = err instanceof Error ? err.message : 'Could not download PDF.'; }
		finally { busy = null; }
	}

	onMount(() => void resolve());
</script>

<div class="print-ws">
	<header class="bar">
		<Tabs active={tab} tabs={[{ id: 'preview', label: 'Preview' }, { id: 'edit', label: 'Edit' }, { id: 'issues', label: 'Issues' }]} onSelect={(id) => (tab = id as typeof tab)} />
		{#if generationId && pageDocumentV2}<Button size="sm" onclick={() => (exportOpen = true)}>Download PDF</Button>{/if}
	</header>
	{#if error && artifact.state !== 'needs_attention'}<InlineError message={error} hint="You can retry or return to the plan." />{/if}
	{#if loading}
		<p class="muted">Loading Print…</p>
	{:else if tab === 'issues'}
		<LessonIssuesPanel {issues} onRetry={retryPrint} />
	{:else if artifact.state === 'not_created'}
		<EmptyState title="Print not created" description="Create a printable booklet from the approved teaching plan.">{#snippet actions()}<Button busy={busy === 'create'} onclick={() => void createPrint()}>{busy === 'create' ? 'Creating…' : 'Create Print'}</Button><a class="link" href={lessonWorkspaceHref(ctx.unitId, ctx.lessonId, 'plan')}>Review plan</a>{/snippet}</EmptyState>
	{:else if tab === 'preview'}
		{#if pageDocumentV2}<div class="doc"><LectioPageDocumentView document={pageDocumentV2} edition="teacher" /></div>{:else}<EmptyState title="Print needs attention" description={error || 'The Print document is unavailable.'}>{#snippet actions()}<Button variant="secondary" busy={busy === 'retry'} onclick={() => void retryPrint()}>Retry preview</Button>{/snippet}</EmptyState>{/if}
	{:else if tab === 'edit'}
		{#if generationId && pageDocumentV2}<PrintDocumentEditor {generationId} document={pageDocumentV2} />{:else}<EmptyState title="Print editor unavailable" description={error || 'The existing Print artifact cannot be loaded.'}>{#snippet actions()}<Button variant="secondary" busy={busy === 'retry'} onclick={() => void retryPrint()}>Retry</Button>{/snippet}</EmptyState>{/if}
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
