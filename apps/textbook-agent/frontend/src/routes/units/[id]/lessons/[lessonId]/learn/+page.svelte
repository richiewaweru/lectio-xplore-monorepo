<script lang="ts">
	import { getContext } from 'svelte';
	import { onMount } from 'svelte';
	import { getBuilderLesson } from '$lib/learn/authoring/builder/api/lesson-crud';
	import { isLearnDocument, type LearnDocument } from '$lib/learn/document/types';
	import DocumentEditor from '$lib/learn/document/DocumentEditor.svelte';
	import {
		publishLearnRelease,
		listLearnReleases,
		type LearnReleaseRecord
	} from '$lib/learn/student/api/releases';
	import { apiFetch } from '$lib/api/client';
	import { ensureOk } from '$lib/api/errors';
	import type { PathLesson, PreparedLessonStatus, Unit, UnitPath } from '$lib/types/units';
	import { Button, Dialog, InlineError, EmptyState, Badge } from '$lib/ui';
	import {
		resolveBuilderLessonId,
		lessonWorkspaceHref
	} from '$lib/curriculum/lessons/lesson-context';
	import { generateLearnRealization } from '$lib/api/units';
	import { realizeLearnFromGeneration } from '$lib/api/v3';

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

	let document = $state<LearnDocument | null>(null);
	let builderLessonId = $state<string | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);
	let busy = $state<string | null>(null);
	let release = $state<LearnReleaseRecord | null>(null);
	let assignOpen = $state(false);
	let classes = $state<Array<{ id: string; name: string }>>([]);
	let assignClassId = $state('');
	let assignMode = $state('rolling');
	let assignStatus = $state<string | null>(null);

	async function resolveAndLoad() {
		loading = true;
		error = null;
		try {
			await ctx.refreshPreparation();
			let id = resolveBuilderLessonId(ctx.preparation) || builderLessonId;
			if (!id && ctx.preparation?.learn_output_id) {
				// Older status payloads expose the native output id rather than the
				// editable builder id. Replaying the idempotent handoff resolves the
				// concrete editable lesson without creating a second realization.
				try {
					const body = await realizeLearnFromGeneration(ctx.preparation.generation_id || '');
					id = body.editable_lesson_id || null;
				} catch {
					id = null;
				}
			}
			if (!id) {
				document = null;
				builderLessonId = null;
				return;
			}
			try {
				const record = await getBuilderLesson(id);
				if (!isLearnDocument(record.document)) {
					error = 'This Learn lesson is not in the expected format.';
					return;
				}
				builderLessonId = id;
				document = record.document;
				const releases = await listLearnReleases(id);
				if (releases.length) {
					release = releases[0] as LearnReleaseRecord;
				}
			} catch {
				document = null;
				builderLessonId = null;
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load Learn lesson.';
		} finally {
			loading = false;
		}
	}

	async function createLearn() {
		if (!ctx.path || !ctx.lesson) return;
		busy = 'create';
		error = null;
		try {
			const gid = ctx.preparation?.generation_id;
			if (gid) {
				const body = await realizeLearnFromGeneration(gid);
				builderLessonId = body.editable_lesson_id;
				await ctx.refreshPreparation();
				await resolveAndLoad();
				return;
			}
			const result = await generateLearnRealization(ctx.unitId, ctx.path, ctx.lesson);
			builderLessonId = result.editable_lesson_id;
			await ctx.refreshPreparation();
			await resolveAndLoad();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not create Learn lesson.';
		} finally {
			busy = null;
		}
	}

	async function publish() {
		if (!builderLessonId) return;
		busy = 'publish';
		error = null;
		try {
			release = await publishLearnRelease(builderLessonId, {
				title: ctx.lesson?.title,
				path_lesson_id: ctx.lessonId
			});
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
			const response = await apiFetch('/api/v1/learn/assignments', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					learn_release_id: release.id,
					title: release.title || ctx.lesson?.title || 'Lesson',
					class_ids: [assignClassId],
					mode: assignMode
				})
			});
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
		<div class="left">
			{#if release}
				<Badge tone="ready">Published · Version {release.release_number}</Badge>
			{/if}
			{#if assignStatus}
				<span class="ok">{assignStatus}</span>
			{/if}
		</div>
		<div class="right">
			{#if builderLessonId}
				<a class="link" href={`/learn/lessons/${encodeURIComponent(builderLessonId)}`}>Preview</a>
				{#if release}
					<Button variant="secondary" size="sm" onclick={() => { assignOpen = true; void loadClasses(); }}>
						Assign to class
					</Button>
				{:else}
					<Button size="sm" busy={busy === 'publish'} onclick={() => void publish()}>
						{busy === 'publish' ? 'Publishing…' : 'Publish'}
					</Button>
				{/if}
			{/if}
		</div>
	</header>

	{#if error}
		<InlineError message={error} />
	{/if}

	{#if loading}
		<p class="muted">Loading Learn lesson…</p>
	{:else if !document || !builderLessonId}
		<EmptyState
			title="No Learn lesson yet"
			description="Create an interactive Learn lesson from the approved teaching plan."
		>
			{#snippet actions()}
				<Button busy={busy === 'create'} onclick={() => void createLearn()}>
					{busy === 'create' ? 'Creating…' : 'Create Learn'}
				</Button>
				<a class="link" href={lessonWorkspaceHref(ctx.unitId, ctx.lessonId, 'plan')}>Review plan</a>
			{/snippet}
		</EmptyState>
	{:else}
		<DocumentEditor
			{document}
			lessonId={builderLessonId}
			previewHref={`/learn/lessons/${encodeURIComponent(builderLessonId)}`}
		/>
	{/if}
</div>

<Dialog bind:open={assignOpen} title="Assign lesson" description="Choose a class. Lectio uses the published version automatically.">
	<label class="field">
		<span>Class</span>
		<select bind:value={assignClassId}>
			{#each classes as row}
				<option value={row.id}>{row.name}</option>
			{/each}
		</select>
	</label>
	<label class="field">
		<span>Mode</span>
		<select bind:value={assignMode}>
			<option value="rolling">Rolling — late joiners get this lesson</option>
			<option value="snapshot">Snapshot — only current students</option>
		</select>
	</label>
	{#snippet footer()}
		<Button variant="secondary" onclick={() => (assignOpen = false)}>Cancel</Button>
		<Button busy={busy === 'assign'} disabled={!assignClassId} onclick={() => void assign()}>
			{busy === 'assign' ? 'Assigning…' : 'Assign lesson'}
		</Button>
	{/snippet}
</Dialog>

<style>
	.learn-ws {
		display: grid;
		gap: var(--space-4);
	}
	.bar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: var(--space-3);
		flex-wrap: wrap;
	}
	.right,
	.left {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		flex-wrap: wrap;
	}
	.link {
		color: var(--accent);
		font-size: 0.875rem;
		font-weight: 550;
		text-decoration: none;
	}
	.muted {
		color: var(--ink-2);
	}
	.ok {
		color: var(--success);
		font-size: 0.8125rem;
	}
	.field {
		display: grid;
		gap: 0.4rem;
		margin-bottom: var(--space-3);
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--ink-2);
	}
	select {
		font: inherit;
		font-weight: 400;
		padding: 0.55rem 0.7rem;
		border-radius: var(--radius-md);
		border: 1px solid var(--rule);
		background: var(--surface);
		color: var(--ink);
	}
</style>
