<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { getBuilderLesson } from '$lib/learn/authoring/builder/api/lesson-crud';
	import { isLearnDocument, type LearnDocument } from '$lib/learn/document/types';
	import DocumentEditor from '$lib/learn/document/DocumentEditor.svelte';
	import StudentLessonShell from '$lib/learn/student/StudentLessonShell.svelte';
	import { publishLearnRelease, listLearnReleases, type LearnReleaseRecord } from '$lib/learn/student/api/releases';
	import { apiFetch } from '$lib/api/client';
	import { ensureOk } from '$lib/api/errors';
	import { getLessonIssues, retryLessonRealization, generateLearnRealization } from '$lib/api/units';
	import type { LessonIssue, PathLesson, PreparedLessonStatus, Unit, UnitPath } from '$lib/types/units';
	import { Button, Dialog, InlineError, EmptyState, Badge, Tabs } from '$lib/ui';
	import { lessonArtifactUi, lessonWorkspaceHref, resolveBuilderLessonId } from '$lib/curriculum/lessons/lesson-context';
	import { realizeLearnFromGeneration } from '$lib/api/v3';
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
	let document = $state<LearnDocument | null>(null);
	let builderLessonId = $state<string | null>(null);
	let loadError = $state<string | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);
	let busy = $state<string | null>(null);
	let issues = $state<LessonIssue[]>([]);
	let release = $state<LearnReleaseRecord | null>(null);
	let assignOpen = $state(false);
	let classes = $state<Array<{ id: string; name: string }>>([]);
	let assignClassId = $state('');
	let assignMode = $state('rolling');
	let assignStatus = $state<string | null>(null);

	const artifact = $derived(lessonArtifactUi(ctx.preparation, 'learn', loadError));

	async function loadIssues(): Promise<void> {
		try {
			issues = (await getLessonIssues(ctx.unitId, ctx.lessonId, 'learn')).issues;
		} catch (err) {
			issues = [{ id: 'issues-load-failed', path: 'learn', severity: 'error', category: 'document', code: 'ISSUES_LOAD_FAILED', message: err instanceof Error ? err.message : 'Could not load Learn issues.', repairable: false, source: 'workspace' }];
		}
	}

	async function resolveAndLoad() {
		loading = true;
		error = null;
		loadError = null;
		try {
			await ctx.refreshPreparation();
			const id = resolveBuilderLessonId(ctx.preparation) || builderLessonId;
			builderLessonId = id;
			if (id) {
				try {
					const record = await getBuilderLesson(id);
					if (!isLearnDocument(record.document)) {
						loadError = 'This Learn artifact exists but is not in the expected document format.';
						document = null;
					} else {
						document = record.document;
						const releases = await listLearnReleases(id);
						release = releases.length ? releases[0] as LearnReleaseRecord : null;
					}
				} catch (err) {
					loadError = err instanceof Error ? err.message : 'Learn preview could not be loaded.';
					document = null;
				}
			} else {
				document = null;
				if (artifact.exists) loadError = 'The Learn artifact exists, but its editable document link is unavailable.';
			}
			await loadIssues();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load Learn lesson.';
		} finally {
			loading = false;
		}
	}

	async function createLearn() {
		if (!ctx.path || !ctx.lesson || artifact.exists) return;
		busy = 'create';
		error = null;
		try {
			const gid = ctx.preparation?.generation_id;
			if (gid) await realizeLearnFromGeneration(gid);
			else await generateLearnRealization(ctx.unitId, ctx.path, ctx.lesson);
			await resolveAndLoad();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not create Learn lesson.';
		} finally {
			busy = null;
		}
	}

	async function retryLearn() {
		if (!ctx.path || !ctx.lesson || !artifact.realizationId) return;
		busy = 'retry';
		try {
			await retryLessonRealization(ctx.unitId, ctx.path, ctx.lesson, artifact.realizationId);
			await resolveAndLoad();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not retry Learn.';
		} finally {
			busy = null;
		}
	}

	async function publish() {
		if (!builderLessonId) return;
		busy = 'publish';
		error = null;
		try {
			release = await publishLearnRelease(builderLessonId, { title: ctx.lesson?.title, path_lesson_id: ctx.lessonId });
			assignOpen = true;
			await loadClasses();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not publish.';
		} finally {
			busy = null;
		}
	}

	async function loadClasses() {
		const response = await apiFetch('/api/v1/learn/classes');
		await ensureOk(response);
		classes = await response.json();
		if (classes[0] && !assignClassId) assignClassId = classes[0].id;
	}

	async function assign() {
		if (!release || !assignClassId) return;
		busy = 'assign';
		assignStatus = null;
		try {
			const response = await apiFetch('/api/v1/learn/assignments', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ learn_release_id: release.id, title: release.title || ctx.lesson?.title || 'Lesson', class_ids: [assignClassId], mode: assignMode }) });
			await ensureOk(response);
			assignStatus = 'Assigned to class.';
			assignOpen = false;
		} catch (err) {
			assignStatus = err instanceof Error ? err.message : 'Could not assign.';
		} finally {
			busy = null;
		}
	}

	onMount(() => void resolveAndLoad());
</script>

<div class="learn-ws">
	<header class="bar">
		<Tabs active={tab} tabs={[{ id: 'preview', label: 'Preview' }, { id: 'edit', label: 'Edit' }, { id: 'issues', label: 'Issues' }]} onSelect={(id) => (tab = id as typeof tab)} />
		<div class="right">
			{#if release}<Badge tone="ready">Published · Version {release.release_number}</Badge>{/if}
			{#if assignStatus}<span class="ok">{assignStatus}</span>{/if}
			{#if builderLessonId && release}<Button variant="secondary" size="sm" onclick={() => { assignOpen = true; void loadClasses(); }}>Assign to class</Button>{:else if builderLessonId}<Button size="sm" busy={busy === 'publish'} onclick={() => void publish()}>{busy === 'publish' ? 'Publishing…' : 'Publish'}</Button>{/if}
		</div>
	</header>

	{#if error}<InlineError message={error} />{/if}
	{#if loading}
		<p class="muted">Loading Learn lesson…</p>
	{:else if tab === 'issues'}
		<LessonIssuesPanel {issues} onRetry={retryLearn} />
	{:else if artifact.state === 'not_created'}
		<EmptyState title="Learn not created" description="Create an interactive Learn lesson from the approved teaching plan.">
			{#snippet actions()}<Button busy={busy === 'create'} onclick={() => void createLearn()}>{busy === 'create' ? 'Creating…' : 'Create Learn'}</Button><a class="link" href={lessonWorkspaceHref(ctx.unitId, ctx.lessonId, 'plan')}>Review plan</a>{/snippet}
		</EmptyState>
	{:else if tab === 'preview'}
		{#if document}<StudentLessonShell {document} preview />{:else}<EmptyState title="Learn needs attention" description={loadError || 'The Learn preview is unavailable.'}>{#snippet actions()}<Button variant="secondary" busy={busy === 'retry'} onclick={() => void retryLearn()}>Retry preview</Button>{/snippet}</EmptyState>{/if}
	{:else if tab === 'edit'}
		{#if builderLessonId && document}<DocumentEditor {document} lessonId={builderLessonId} previewHref={`/learn/lessons/${encodeURIComponent(builderLessonId)}`} />{:else}<EmptyState title="Builder unavailable" description={loadError || 'The existing Learn artifact has no editable document available.'}>{#snippet actions()}<Button variant="secondary" busy={busy === 'retry'} onclick={() => void retryLearn()}>Retry</Button>{/snippet}</EmptyState>{/if}
	{/if}
</div>

<Dialog bind:open={assignOpen} title="Assign lesson" description="Choose a class. Lectio uses the published version automatically.">
	<label class="field"><span>Class</span><select bind:value={assignClassId}>{#each classes as row}<option value={row.id}>{row.name}</option>{/each}</select></label>
	<label class="field"><span>Mode</span><select bind:value={assignMode}><option value="rolling">Rolling — late joiners get this lesson</option><option value="snapshot">Snapshot — only current students</option></select></label>
	{#snippet footer()}<Button variant="secondary" onclick={() => (assignOpen = false)}>Cancel</Button><Button busy={busy === 'assign'} disabled={!assignClassId} onclick={() => void assign()}>{busy === 'assign' ? 'Assigning…' : 'Assign lesson'}</Button>{/snippet}
</Dialog>

<style>
	.learn-ws { display: grid; gap: var(--space-4); }
	.bar, .right { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
	.bar { justify-content: space-between; align-items: flex-start; }
	.bar :global(.tabs) { flex: 1; margin-bottom: 0; }
	.link { color: var(--accent); font-size: 0.875rem; font-weight: 550; text-decoration: none; }
	.muted, .ok { color: var(--ink-2); }
	.ok { color: var(--success); font-size: 0.8125rem; }
	.field { display: grid; gap: 0.4rem; margin-bottom: var(--space-3); font-size: 0.8125rem; font-weight: 600; color: var(--ink-2); }
	select { font: inherit; font-weight: 400; padding: 0.55rem 0.7rem; border-radius: var(--radius-md); border: 1px solid var(--rule); background: var(--surface); color: var(--ink); }
</style>
