<script lang="ts">
	import {
		getPublishCandidates,
		listTeacherClasses,
		publishUnitToClass,
		type PublishCandidate,
		type PublishItemResult,
		type TeacherClass
	} from '$lib/api/topic-publish';
	import { Button, Dialog, InlineError } from '$lib/ui';

	interface Props {
		open: boolean;
		unitId: string;
		unitTitle: string;
	}

	let { open = $bindable(false), unitId, unitTitle }: Props = $props();

	let classes = $state<TeacherClass[]>([]);
	let classId = $state('');
	let candidates = $state<PublishCandidate[]>([]);
	let selected = $state<Record<string, boolean>>({});
	let results = $state<PublishItemResult[] | null>(null);
	let loadingClasses = $state(false);
	let loadingLessons = $state(false);
	let publishing = $state(false);
	let error = $state<string | null>(null);

	const chosen = $derived(candidates.filter((c) => c.generated && selected[c.path_lesson_id]));

	$effect(() => {
		if (open) void init();
	});

	async function init() {
		results = null;
		error = null;
		loadingClasses = true;
		try {
			classes = await listTeacherClasses();
			classId = classes[0]?.id ?? '';
			if (classId) await loadCandidates();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load classes.';
		} finally {
			loadingClasses = false;
		}
	}

	async function loadCandidates() {
		loadingLessons = true;
		error = null;
		try {
			const response = await getPublishCandidates(unitId, classId);
			candidates = response.lessons;
			selected = Object.fromEntries(response.lessons.map((c) => [c.path_lesson_id, c.generated]));
		} catch (err) {
			candidates = [];
			error = err instanceof Error ? err.message : 'Could not load the topic lessons.';
		} finally {
			loadingLessons = false;
		}
	}

	async function onClassChange() {
		results = null;
		await loadCandidates();
	}

	async function publish() {
		if (!classId || chosen.length === 0) return;
		publishing = true;
		error = null;
		try {
			const response = await publishUnitToClass(unitId, {
				class_id: classId,
				path_lesson_ids: chosen.map((c) => c.path_lesson_id)
			});
			results = response.results;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not publish the topic.';
		} finally {
			publishing = false;
		}
	}

	const statusLabel: Record<PublishItemResult['status'], string> = {
		published: 'Published',
		already_published: 'Already published',
		not_generated: 'Not generated',
		failed: 'Failed'
	};
</script>

<Dialog bind:open title={`Publish "${unitTitle}" to a class`} description="Students see every lesson on the topic path. Lessons not published yet show as Being prepared.">
	{#if error}<InlineError message={error} />{/if}
	{#if results}
		<ul class="results" aria-label="Publish results">
			{#each results as row (row.path_lesson_id)}
				<li class={row.status}>
					<span class="num">{row.position + 1}</span>
					<span class="title">{row.title}</span>
					<span class="state">{statusLabel[row.status]}</span>
					{#if row.message}<span class="msg">{row.message}</span>{/if}
				</li>
			{/each}
		</ul>
	{:else}
		{#if loadingClasses}
			<p class="muted">Loading classes…</p>
		{:else if classes.length === 0}
			<p class="muted">Create a class first, then publish this topic to it.</p>
		{:else}
			<label class="field">
				<span>Class</span>
				<select bind:value={classId} onchange={() => void onClassChange()}>
					{#each classes as row (row.id)}<option value={row.id}>{row.name}</option>{/each}
				</select>
			</label>
			<fieldset class="lessons">
				<legend>Lessons</legend>
				{#if loadingLessons}
					<p class="muted">Loading lessons…</p>
				{:else}
					{#each candidates as row (row.path_lesson_id)}
						<label class="lesson" class:off={!row.generated}>
							<input type="checkbox" bind:checked={selected[row.path_lesson_id]} disabled={!row.generated} />
							<span class="num">{row.position + 1}</span>
							<span class="title">{row.title}</span>
							{#if !row.generated}
								<span class="tag">not generated</span>
								<span class="hint">Students will see "Being prepared".</span>
							{:else if row.status === 'published'}
								<span class="tag">published</span>
							{:else if row.has_unpublished_changes}
								<span class="tag">changed</span>
							{/if}
						</label>
					{/each}
				{/if}
			</fieldset>
		{/if}
	{/if}
	{#snippet footer()}
		{#if results}
			<Button onclick={() => (open = false)}>Done</Button>
		{:else}
			<Button variant="secondary" onclick={() => (open = false)}>Cancel</Button>
			<Button busy={publishing} disabled={!classId || chosen.length === 0 || loadingLessons} onclick={() => void publish()}>{publishing ? 'Publishing…' : 'Publish'}</Button>
		{/if}
	{/snippet}
</Dialog>

<style>
	.field { display: grid; gap: 0.4rem; margin-bottom: var(--space-3); font-size: 0.8125rem; font-weight: 600; color: var(--ink-2); }
	select { font: inherit; font-weight: 400; padding: 0.55rem 0.7rem; border-radius: var(--radius-md); border: 1px solid var(--rule); background: var(--surface); color: var(--ink); }
	.lessons { border: 0; padding: 0; margin: 0; display: grid; gap: 0.5rem; }
	.lessons legend { padding: 0; margin-bottom: 0.4rem; font-size: 0.8125rem; font-weight: 600; color: var(--ink-2); }
	.lesson { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.5rem; font-size: 0.875rem; }
	.lesson.off { color: var(--ink-3); }
	.num { font: 500 0.75rem 'IBM Plex Mono', monospace; color: var(--ink-3); }
	.tag { font: 500 0.6875rem 'IBM Plex Mono', monospace; text-transform: uppercase; color: var(--ink-3); }
	.hint, .msg, .muted { color: var(--ink-2); font-size: 0.8125rem; }
	.results { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.6rem; }
	.results li { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.5rem; font-size: 0.875rem; }
	.state { font-weight: 600; color: var(--success); }
	li.failed .state { color: var(--danger); }
	li.not_generated .state, li.already_published .state { color: var(--ink-2); }
</style>
