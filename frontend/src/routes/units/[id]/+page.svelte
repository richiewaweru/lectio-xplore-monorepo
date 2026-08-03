<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { isApiError } from '$lib/api/errors';
	import {
		approveUnitPath,
		editUnitPathByChat,
		getPreparedLessonStatus,
		getHistoricalPath,
		getPathHistory,
		getPathStatus,
		getTeachingSchedule,
		getLessonShape,
		getUnit,
		getUnitGroups,
		getUnitPath,
		listUnitResources,
		mergePathLessons,
		patchPathLesson,
		planUnitPath,
		preparePathLesson,
		regeneratePathLesson,
		restorePathVersion
	} from '$lib/api/units';
	import TeachingSchedulePanel from '$lib/components/units/TeachingSchedulePanel.svelte';
	import UnitGroupsPanel from '$lib/components/units/UnitGroupsPanel.svelte';
	import LessonShapePanel from '$lib/components/units/LessonShapePanel.svelte';
	import LessonVersionsPanel from '$lib/components/units/LessonVersionsPanel.svelte';
	import LessonResultsPanel from '$lib/components/units/LessonResultsPanel.svelte';
	import ResourceComposerPanel from '$lib/components/units/ResourceComposerPanel.svelte';
	import type {
		LessonMode,
		MergeCriticResult,
		PathLesson,
		PathStatusAggregate,
		PathVersionSummary,
		PreparedLessonStatus,
		ResourceComposition,
		LessonShapePreview,
		TeachingSchedule,
		Unit,
		UnitGroups,
		UnitPath
	} from '$lib/types/units';

	const unitId = $derived(page.params.id ?? '');
	let unit = $state<Unit | null>(null);
	let path = $state<UnitPath | null>(null);
	let selectedId = $state<string | null>(null);
	let loading = $state(true);
	let busy = $state<string | null>(null);
	let error = $state<string | null>(null);
	let lessonMode = $state<LessonMode>('first_exposure');
	let shape = $state<LessonShapePreview | null>(null);
	let misconceptionCount = $state(1);
	let preparation = $state<PreparedLessonStatus | null>(null);
	let history = $state<PathVersionSummary[]>([]);
	let aggregate = $state<PathStatusAggregate | null>(null);
	let viewedVersion = $state<UnitPath | null>(null);
	let schedule = $state<TeachingSchedule | null>(null);
	let groups = $state<UnitGroups | null>(null);
	let compositions = $state<ResourceComposition[]>([]);
	let selectedGroupIds = $state<string[]>([]);
	let activeView = $state<'path' | 'schedule' | 'groups' | 'results' | 'resources'>('path');
	let restoreReason = $state('Restore this version as a new editable draft.');
	let pendingAction = $state<{ label: string; description: string; run: () => Promise<void> } | null>(null);
	let regenerationReason = $state('The lesson changed after preparation.');
	let editTitle = $state('');
	let editObjective = $state('');
	let editMustEstablish = $state('');
	let editExclusions = $state('');
	let dismissedMergeKeys = $state<Set<string>>(new Set());
	let chatMessage = $state('');
	let chatBusy = $state(false);
	let chatUnavailable = $state(false);
	let chatNote = $state<string | null>(null);
	let showVersions = $state(false);
	const debugMode = import.meta.env.DEV;

	const selected = $derived(path?.lessons.find((lesson) => lesson.id === selectedId) ?? null);
	const canLockIn = $derived(Boolean(path?.reaches_destination) && (path?.prerequisite_risks.length ?? 0) === 0);
	const lockBlockReason = $derived.by(() => {
		if (!path) return '';
		if (path.prerequisite_risks.length > 0) return "Something in this route relies on knowledge that isn't taught yet — fix that before locking it in.";
		if (!path.reaches_destination) return "This route doesn't reach the destination yet.";
		return '';
	});
	const mergeQuestions = $derived.by(() => {
		if (!path) return [] as Array<{ key: string; result: MergeCriticResult; lessonA: PathLesson; lessonB: PathLesson }>;
		const bySlug = new Map(path.lessons.map((lesson) => [lesson.concept_slug, lesson]));
		return path.merge_critic_results
			.filter((result) => result.verdict === 'teacher_decision' || result.verdict === 'merge_suggested')
			.map((result) => ({
				key: `${result.lesson_a}|${result.lesson_b}`,
				result,
				lessonA: bySlug.get(result.lesson_a) ?? null,
				lessonB: bySlug.get(result.lesson_b) ?? null
			}))
			.filter(
				(entry): entry is { key: string; result: MergeCriticResult; lessonA: PathLesson; lessonB: PathLesson } =>
					Boolean(entry.lessonA && entry.lessonB) && !dismissedMergeKeys.has(entry.key)
			);
	});

	function lines(value: string): string[] {
		return value.split('\n').map((item) => item.trim()).filter(Boolean);
	}

	function slug(value: string): string {
		return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '.').replace(/^\.|\.$/g, '') || 'teacher.part';
	}

	function plannerInput(current: Unit) {
		return {
			topic: current.topic,
			subject: current.subject,
			grade_level: current.grade_level,
			destination_objective: current.destination_objective,
			starting_knowledge: current.starting_knowledge,
			curriculum_context: current.curriculum_context,
			must_include: [],
			must_avoid: [],
			terminology: [],
			notation: null,
			assessment_context: null,
			known_difficulties: []
		};
	}

	function dependencySentences(lesson: PathLesson | null): string[] {
		if (!lesson || !path) return [];
		const sentences: string[] = [];
		for (const prerequisiteId of lesson.prerequisites) {
			const prerequisite = path.lessons.find((candidate) => candidate.id === prerequisiteId);
			if (prerequisite) sentences.push(`needs lesson ${prerequisite.position + 1}`);
		}
		for (const external of lesson.external_prerequisites) {
			sentences.push(external);
		}
		return sentences;
	}

	function fillEditor(lesson: PathLesson): void {
		editTitle = lesson.title;
		editObjective = lesson.objective;
		editMustEstablish = lesson.must_establish.join('\n');
		editExclusions = lesson.exclusions.join('\n');
	}

	async function selectLesson(lesson: PathLesson): Promise<void> {
		selectedId = lesson.id;
		fillEditor(lesson);
		shape = null;
		preparation = null;
		try {
			[shape, preparation] = await Promise.all([
				getLessonShape(unitId, lesson.id, lessonMode, misconceptionCount),
				getPreparedLessonStatus(unitId, lesson.id)
			]);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load lesson details.';
		}
	}

	async function updateShapeSettings(mode: LessonMode, count: number): Promise<void> {
		if (!selected) return;
		lessonMode = mode;
		misconceptionCount = count;
		shape = null;
		try {
			shape = await getLessonShape(unitId, selected.id, lessonMode, misconceptionCount);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load this lesson shape.';
		}
	}

	async function updateShapeRevision(revision: number): Promise<void> {
		if (!selected) return;
		selected.revision = revision;
		preparation = await getPreparedLessonStatus(unitId, selected.id);
	}

	async function load(options: { preserveSelection?: boolean } = {}): Promise<void> {
		loading = true;
		error = null;
		try {
			unit = await getUnit(unitId);
			groups = await getUnitGroups(unitId);
			selectedGroupIds = groups.groups.map((group) => group.id);
			if (unit.active_path_version_id) {
				[path, history, aggregate, schedule, compositions] = await Promise.all([
					getUnitPath(unitId), getPathHistory(unitId), getPathStatus(unitId),
					getTeachingSchedule(unitId), listUnitResources(unitId)
				]);
			} else {
				path = null; history = []; aggregate = null; schedule = null; compositions = [];
			}
			if (path?.lessons.length) {
				const target = options.preserveSelection
					? path.lessons.find((lesson) => lesson.id === selectedId) ?? path.lessons[0]
					: path.lessons[0];
				await selectLesson(target);
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load the unit workspace.';
		} finally {
			loading = false;
		}
	}

	async function act(label: string, action: () => Promise<unknown>, reload = true): Promise<void> {
		busy = label;
		error = null;
		try {
			await action();
			if (reload) await load({ preserveSelection: true });
		} catch (err) {
			error = err instanceof Error ? err.message : 'That change did not go through.';
		} finally {
			busy = null;
		}
	}

	async function planOrReplan(replan: boolean): Promise<void> {
		if (!unit) return;
		await act(replan ? 'replan' : 'plan', async () => {
			path = await planUnitPath(unitId, plannerInput(unit as Unit), replan, path ?? undefined);
			unit = await getUnit(unitId);
			if (path.lessons.length) await selectLesson(path.lessons[0]);
		}, false);
	}

	async function saveLesson(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (!selected) return;
		await act('save', () => patchPathLesson(unitId, path as UnitPath, selected, {
			title: editTitle.trim(), objective: editObjective.trim(),
			must_establish: lines(editMustEstablish), exclusions: lines(editExclusions)
		}));
	}

	async function combineLessons(question: { key: string; result: MergeCriticResult; lessonA: PathLesson; lessonB: PathLesson }): Promise<void> {
		if (!path) return;
		const { lessonA, lessonB, result } = question;
		const mergedTitle = `${lessonA.title} and ${lessonB.title}`;
		await act('merge', () => mergePathLessons(unitId, path as UnitPath, [lessonA, lessonB], [lessonA.id, lessonB.id], {
			concept_candidate: { slug: slug(mergedTitle), title: mergedTitle },
			objective: result.merged_objective?.trim() || `${lessonA.objective} ${lessonB.objective}`,
			must_establish: [...lessonA.must_establish, ...lessonB.must_establish],
			exclusions: [...new Set([...lessonA.exclusions, ...lessonB.exclusions])],
			primary_knowledge_type: lessonA.primary_knowledge_type,
			secondary_demand: lessonA.secondary_demand
		}));
		dismissedMergeKeys = new Set([...dismissedMergeKeys, question.key]);
	}

	function dismissMergeQuestion(key: string): void {
		dismissedMergeKeys = new Set([...dismissedMergeKeys, key]);
	}

	async function sendChatEdit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (!path || chatUnavailable || chatMessage.trim().length < 2) return;
		chatBusy = true;
		error = null;
		chatNote = null;
		try {
			const result = await editUnitPathByChat(unitId, path, chatMessage.trim());
			chatMessage = '';
			chatNote = result.issues?.length ? result.issues.join(' ') : (result.note ?? null);
			await load({ preserveSelection: true });
		} catch (err) {
			if (isApiError(err) && err.status === 404) {
				chatUnavailable = true;
			} else {
				error = err instanceof Error ? err.message : 'Could not update the lessons from that message.';
			}
		} finally {
			chatBusy = false;
		}
	}

	async function prepare(): Promise<void> {
		if (!selected) return;
		await act('prepare', async () => {
			const prepared = await preparePathLesson(unitId, path as UnitPath, selected, lessonMode, selectedGroupIds);
			window.location.href = `/studio?generation_id=${encodeURIComponent(prepared.generation_id)}`;
		}, false);
	}

	async function regenerate(): Promise<void> {
		if (!selected || regenerationReason.trim().length < 3) return;
		await act('regenerate', async () => {
			const prepared = await regeneratePathLesson(
				unitId,
				path as UnitPath,
				selected,
				lessonMode,
				regenerationReason.trim(),
				selectedGroupIds
			);
			window.location.href = `/studio?generation_id=${encodeURIComponent(prepared.generation_id)}`;
		}, false);
	}

	async function viewVersion(version: PathVersionSummary): Promise<void> {
		error = null;
		try { viewedVersion = await getHistoricalPath(unitId, version.id); }
		catch (err) { error = err instanceof Error ? err.message : 'Could not load path history.'; }
	}

	function confirmRestore(version: PathVersionSummary): void {
		if (!path || version.id === path.id) return;
		pendingAction = {
			label: `Restore path v${version.version}`,
			description: 'A new editable draft will be created. Nothing in history is deleted.',
			run: () => act('restore', () => restorePathVersion(unitId, version.id, path as UnitPath, restoreReason))
		};
	}

	async function runPendingAction(): Promise<void> {
		const action = pendingAction;
		pendingAction = null;
		if (action) await action.run();
	}

	onMount(() => void load());
</script>

<svelte:head><title>{unit ? `${unit.title} · Units` : 'Unit · Lectio'}</title></svelte:head>

<div class="unit-page">
	{#if loading && !unit}
		<p class="loading" role="status">Loading unit…</p>
	{:else if unit}
		<header class="unit-head">
			<div><a href="/units" class="back">← Units</a><p class="eyebrow">{unit.subject} · {unit.grade_level}</p><h1>{unit.title}</h1><p>{unit.destination_objective}</p></div>
			<div class="head-actions">
				{#if path}<span class:approved={path.status === 'approved'}>{path.status === 'approved' ? 'Locked in' : 'Draft'}</span>{/if}
				<button class="secondary" type="button" disabled={busy !== null} onclick={() => planOrReplan(Boolean(path))}>{busy === 'replan' || busy === 'plan' ? 'Planning…' : path ? 'Replan the lessons' : 'Plan the lessons'}</button>
			</div>
		</header>

		{#if error}<p class="error" role="alert">{error}</p>{/if}

		{#if !path}
			<section class="empty"><p class="eyebrow">Destination saved</p><h2>Build your lessons</h2><p>This turns your destination into a numbered list of lessons, checking that every earlier lesson leads somewhere before the next one needs it.</p><button class="primary" type="button" disabled={busy !== null} onclick={() => planOrReplan(false)}>{busy === 'plan' ? 'Planning your lessons…' : 'Plan the lessons'}</button></section>
		{:else}
			<nav class="view-tabs" aria-label="Unit workspace views">
				<button type="button" class:active={activeView === 'path'} aria-current={activeView === 'path' ? 'page' : undefined} onclick={() => (activeView = 'path')}>Your lessons</button>
				<button type="button" class:active={activeView === 'schedule'} aria-current={activeView === 'schedule' ? 'page' : undefined} onclick={() => (activeView = 'schedule')}>Schedule <span>{schedule?.periods.length ?? 0}</span></button>
				<button type="button" class:active={activeView === 'groups'} aria-current={activeView === 'groups' ? 'page' : undefined} onclick={() => (activeView = 'groups')}>Groups <span>{groups?.groups.length ?? 0}</span></button>
				<button type="button" class:active={activeView === 'results'} aria-current={activeView === 'results' ? 'page' : undefined} onclick={() => (activeView = 'results')}>Results</button>
				<button type="button" class:active={activeView === 'resources'} aria-current={activeView === 'resources' ? 'page' : undefined} onclick={() => (activeView = 'resources')}>Resources <span>{compositions.length}</span></button>
			</nav>
			{#if activeView === 'path'}
			<section class="lock-in-bar">
				<p>{path.lessons.length} {path.lessons.length === 1 ? 'lesson' : 'lessons'}</p>
				{#if path.status !== 'approved'}
					<div class="lock-in">
						<button class="primary" type="button" disabled={busy !== null || !canLockIn} onclick={() => act('approve', async () => { path = await approveUnitPath(unitId, path as UnitPath); unit = await getUnit(unitId); await load({ preserveSelection: true }); }, false)}>{busy === 'approve' ? 'Locking it in…' : 'Looks good — lock it in'}</button>
						{#if !canLockIn}<p class="lock-reason">{lockBlockReason}</p>{/if}
					</div>
				{/if}
			</section>

			{#if mergeQuestions.length}
				<section class="merge-questions" aria-label="Merge suggestions">
					{#each mergeQuestions as question (question.key)}
						<div class="merge-question">
							<p>Lessons {question.lessonA.position + 1} and {question.lessonB.position + 1} might work as one lesson — {question.result.reason}</p>
							<div class="merge-actions">
								<button type="button" class="secondary" disabled={busy !== null} onclick={() => dismissMergeQuestion(question.key)}>Keep apart</button>
								<button type="button" class="primary" disabled={busy !== null} onclick={() => combineLessons(question)}>Combine</button>
							</div>
						</div>
					{/each}
				</section>
			{/if}

			{#if aggregate}
				<section class="status-board" aria-label="Lesson preparation status">
					{#each Object.entries(aggregate.counts) as [state, count]}
						<div class:attention={state === 'failed' || state === 'stale' || state === 'warning'}><strong>{count}</strong><span>{state.replace('_', ' ')}</span></div>
					{/each}
				</section>
			{/if}

			<section class="history-panel">
				<div class="section-head"><div><p class="eyebrow">Lesson history</p><h2>Recoverable versions</h2></div><p>Structural edits create a new draft. Older routes remain available.</p></div>
				<div class="history-list">{#each history as version}<article class:current={version.id === path.id}><div><strong>v{version.version}</strong><span>{version.status}</span><small>{version.generated_by}</small></div><div class="history-actions"><button type="button" class="text-button" onclick={() => viewVersion(version)}>Inspect</button>{#if version.id !== path.id}<button type="button" class="text-button" onclick={() => confirmRestore(version)}>Restore</button>{/if}</div></article>{/each}</div>
				{#if viewedVersion}<div class="history-preview"><div><strong>v{viewedVersion.version}</strong><span>{viewedVersion.status} · {viewedVersion.lessons.length} lessons</span></div><ol>{#each viewedVersion.lessons as lesson}<li>{lesson.title}</li>{/each}</ol><button type="button" class="text-button" onclick={() => (viewedVersion = null)}>Close preview</button></div>{/if}
			</section>

			<div class="workspace">
				<aside class="path-list" aria-label="Your lessons">
					<p class="eyebrow">Your lessons</p>
					<ol>{#each path.lessons as lesson, index (lesson.id)}<li class:active={lesson.id === selectedId} class:skipped={lesson.skipped}><button type="button" onclick={() => selectLesson(lesson)}><span>{index + 1}</span><span><strong>{lesson.title}</strong>{#if dependencySentences(lesson).length}<small>{dependencySentences(lesson).join(' · ')}</small>{:else if lesson.pack_id}<small>prepared</small>{/if}</span></button></li>{/each}</ol>
				</aside>

				{#if selected}
					<main class="inspector">
						<div class="inspector-head"><div><p class="eyebrow">Lesson {selected.position + 1}</p><h2>{selected.title}</h2></div></div>

						<form class="editor" onsubmit={saveLesson}>
							<label><span>Title</span><input bind:value={editTitle} required /></label>
							<label><span>What students will be able to do</span><textarea bind:value={editObjective} required></textarea></label>
							<div class="two"><label><span>Must teach <small>one per line</small></span><textarea bind:value={editMustEstablish} required></textarea></label><label><span>Save for later <small>one per line</small></span><textarea bind:value={editExclusions}></textarea></label></div>
							<button class="secondary" type="submit" disabled={busy !== null}>{busy === 'save' ? 'Saving…' : 'Save lesson changes'}</button>
						</form>

						<section class="dependencies"><div><p class="eyebrow">Before this lesson</p><h3>What it needs first</h3></div>{#if dependencySentences(selected).length}<ul>{#each dependencySentences(selected) as sentence}<li>{sentence}</li>{/each}</ul>{:else}<p>Nothing — this can be the starting point.</p>{/if}</section>

						{#if debugMode}
							{#if shape}
								<LessonShapePanel
									{unitId}
									{path}
									lesson={selected}
									{shape}
									{lessonMode}
									{misconceptionCount}
									{debugMode}
									onsettings={updateShapeSettings}
									onshape={(value) => (shape = value)}
									onrevision={updateShapeRevision}
								/>
							{:else}
								<section class="shape"><p>Loading this lesson's shape…</p></section>
							{/if}
						{/if}

						<section class="prepare">
							<div><p class="eyebrow">Preparation</p><h3>{preparation?.workflow_stage ?? 'Checking status…'}</h3><p>{preparation?.stale ? 'This lesson changed since it was last written and needs to be made again.' : 'This starts the lesson-writing review before anything is generated.'}</p></div>
							{#if preparation?.stale && preparation.can_regenerate}
								<form class="regenerate" onsubmit={(event) => { event.preventDefault(); void regenerate(); }}>
									<label><span>What changed</span><input bind:value={regenerationReason} minlength="3" maxlength="500" required /></label>
									<button class="primary" type="submit" disabled={busy !== null || !shape?.can_prepare || regenerationReason.trim().length < 3}>{busy === 'regenerate' ? 'Making it again…' : 'Make it again'}</button>
								</form>
							{:else if preparation?.generation_id}
								<div class="ready-actions">
									<a class="primary link" href={`/studio?generation_id=${encodeURIComponent(preparation.generation_id)}`}>Open review</a>
									<a class="secondary link" href={`/studio/print/${encodeURIComponent(preparation.generation_id)}`}>Print</a>
									<button class="secondary" type="button" onclick={() => (showVersions = true)}>Make versions for my groups</button>
								</div>
							{:else}<button class="primary" type="button" disabled={path.status !== 'approved' || selected.skipped || busy !== null || !shape?.can_prepare} onclick={prepare}>{busy === 'prepare' ? 'Making the lesson…' : 'Make the lesson'}</button>{/if}
						</section>
					</main>
				{/if}
			</div>

			<section class="chat-edit" aria-label="Edit your lessons by chat">
				<p class="eyebrow">Edit your lessons</p>
				{#if chatUnavailable}
					<p class="chat-disabled">Editing lessons by chat isn't available yet — use the lesson tools above for now.</p>
				{:else}
					<form onsubmit={sendChatEdit}>
						<input bind:value={chatMessage} placeholder="e.g. Combine lessons 2 and 3, or add something about fractions" disabled={chatBusy} />
						<button class="primary" type="submit" disabled={chatBusy || chatMessage.trim().length < 2}>{chatBusy ? 'Updating…' : 'Send'}</button>
					</form>
					{#if chatNote}<p class="chat-note">{chatNote}</p>{/if}
				{/if}
			</section>
			{:else if activeView === 'schedule' && schedule}
				<TeachingSchedulePanel {unitId} {path} {schedule} onsaved={(saved) => (schedule = saved)} />
			{:else if activeView === 'groups' && groups}
				<UnitGroupsPanel {unitId} {groups} onsaved={(saved) => { groups = saved; selectedGroupIds = saved.groups.map((group) => group.id); }} />
			{:else if activeView === 'results'}
				<LessonResultsPanel {unitId} {path} lessons={path.lessons} {groups} />
			{:else if activeView === 'resources'}
				<ResourceComposerPanel {unitId} {path} lessons={path.lessons} {groups} {schedule} {compositions} oncreated={(created) => (compositions = [created, ...compositions])} />
			{/if}
		{/if}
	{/if}
</div>

{#if showVersions && groups}
	<LessonVersionsPanel
		{unitId}
		{groups}
		onsaved={(saved) => { groups = saved; selectedGroupIds = saved.groups.map((group) => group.id); }}
		onclose={() => (showVersions = false)}
	/>
{/if}

{#if pendingAction}
	<div class="confirm-backdrop" role="presentation">
		<div class="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
			<p class="eyebrow">Confirm structural change</p><h2 id="confirm-title">{pendingAction.label}</h2><p>{pendingAction.description}</p>
			{#if pendingAction.label.startsWith('Restore')}<label><span>Recovery reason</span><input bind:value={restoreReason} minlength="3" required /></label>{/if}
			<div><button type="button" class="secondary" onclick={() => (pendingAction = null)}>Cancel</button><button type="button" class="primary" disabled={busy !== null || (pendingAction.label.startsWith('Restore') && restoreReason.trim().length < 3)} onclick={runPendingAction}>Confirm</button></div>
		</div>
	</div>
{/if}

<style>
	.unit-page { min-height: calc(100vh - 58px); padding: 38px 28px 80px; }
	.unit-head, .view-tabs, .lock-in-bar, .merge-questions, .status-board, .history-panel, .workspace, .chat-edit, .empty, .error, .loading { max-width: 1180px; margin-inline: auto; }
	.unit-head { display: flex; align-items: end; justify-content: space-between; gap: 24px; margin-bottom: 28px; }
	.back { display: inline-block; margin-bottom: 18px; color: var(--accent); font-size: 13px; font-weight: 600; text-decoration: none; }
	.eyebrow { margin: 0 0 6px; color: var(--ink-3); font: 500 10px 'IBM Plex Mono', monospace; letter-spacing: .1em; text-transform: uppercase; }
	h1 { margin: 0; font: 500 36px/1.1 Fraunces, Georgia, serif; letter-spacing: -.03em; }
	.unit-head p:last-child { max-width: 720px; margin: 9px 0 0; color: var(--ink-2); font-size: 14px; line-height: 1.5; }
	.head-actions { display: flex; align-items: center; gap: 10px; }
	.head-actions > span { border-radius: 999px; background: var(--amber-soft); color: var(--amber); font: 500 10px 'IBM Plex Mono', monospace; padding: 6px 9px; text-transform: uppercase; }
	.head-actions > span.approved { background: var(--accent-soft); color: var(--accent); }
	button, input, textarea, select { font: inherit; }
	.primary, .secondary, .text-button { cursor: pointer; }
	.primary, .secondary { border-radius: 7px; font-size: 13px; font-weight: 600; padding: 9px 13px; }
	.primary { border: 1px solid var(--accent); background: var(--accent); color: white; }
	.primary.link, .secondary.link { display: inline-block; text-decoration: none; }
	.secondary { border: 1px solid var(--rule); background: var(--surface); color: var(--ink); }
	button:disabled { cursor: not-allowed; opacity: .45; }
	.view-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--rule); margin-bottom: 22px; }
	.view-tabs button { border: 0; border-bottom: 2px solid transparent; background: transparent; color: var(--ink-3); cursor: pointer; padding: 10px 13px; font-size: 12px; font-weight: 600; }
	.view-tabs button.active { border-bottom-color: var(--accent); color: var(--accent); }
	.view-tabs span { display: inline-grid; place-items: center; min-width: 17px; height: 17px; border-radius: 999px; background: var(--paper); margin-left: 4px; font-size: 9px; }
	.lock-in-bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); margin-bottom: 18px; padding: 16px 18px; }
	.lock-in-bar p { margin: 0; color: var(--ink-2); font-size: 13px; }
	.lock-in { display: grid; justify-items: end; gap: 6px; }
	.lock-reason { max-width: 360px; margin: 0; color: var(--ink-3); font-size: 11px; text-align: right; }
	.merge-questions { display: grid; gap: 8px; margin-bottom: 18px; }
	.merge-question { display: flex; align-items: center; justify-content: space-between; gap: 16px; border: 1px solid #dfb294; border-radius: 8px; background: #fff7ed; padding: 12px 14px; }
	.merge-question p { margin: 0; color: #7b4625; font-size: 13px; line-height: 1.5; }
	.merge-actions { display: flex; gap: 8px; flex-shrink: 0; }
	.status-board { display: grid; grid-template-columns: repeat(8, minmax(0, 1fr)); gap: 6px; margin-bottom: 14px; }
	.status-board div { display: grid; gap: 2px; border: 1px solid var(--rule); border-radius: 7px; background: var(--surface); padding: 9px 10px; }
	.status-board div.attention { border-color: #dfb294; background: #fff7ed; }
	.status-board strong { font: 500 18px Fraunces, Georgia, serif; }
	.status-board span { color: var(--ink-3); font-size: 9px; text-transform: uppercase; }
	.history-panel { border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); margin-bottom: 22px; padding: 18px; }
	.history-panel .section-head > p { max-width: 430px; margin: 0; color: var(--ink-3); font-size: 11px; text-align: right; }
	.history-list { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 13px; }
	.history-list article { display: flex; align-items: center; gap: 14px; border: 1px solid var(--rule); border-radius: 7px; padding: 8px 10px; }
	.history-list article.current { border-color: var(--accent); background: var(--accent-soft); }
	.history-list article > div:first-child { display: grid; grid-template-columns: auto auto; column-gap: 6px; align-items: baseline; }
	.history-list article span, .history-list article small { color: var(--ink-3); font-size: 9px; text-transform: uppercase; }
	.history-list article small { grid-column: 1 / -1; margin-top: 2px; text-transform: none; }
	.history-actions { display: flex; gap: 4px; }
	.history-preview { display: grid; gap: 10px; border-top: 1px solid var(--rule); margin-top: 15px; padding-top: 15px; }
	.history-preview > div { display: flex; gap: 8px; align-items: baseline; }
	.history-preview span { color: var(--ink-3); font-size: 11px; }
	.history-preview ol { display: flex; flex-wrap: wrap; gap: 5px 20px; margin: 0; padding-left: 20px; color: var(--ink-2); font-size: 11px; }
	.history-preview button { justify-self: start; }
	.workspace { display: grid; grid-template-columns: 300px minmax(0, 1fr); align-items: start; gap: 22px; }
	.path-list { position: sticky; top: 80px; border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); padding: 15px; }
	.path-list ol { display: grid; gap: 3px; margin: 0; padding: 0; list-style: none; }
	.path-list li button { display: grid; grid-template-columns: 24px minmax(0, 1fr); gap: 7px; width: 100%; border: 0; border-radius: 7px; background: transparent; color: var(--ink); padding: 9px; text-align: left; }
	.path-list li button > span:first-child { display: grid; place-items: center; width: 20px; height: 20px; border-radius: 50%; background: var(--paper); color: var(--ink-3); font: 500 10px 'IBM Plex Mono', monospace; }
	.path-list li button strong, .path-list li button small { display: block; }
	.path-list li button strong { font-size: 13px; }
	.path-list li button small { margin-top: 3px; color: var(--ink-3); font-size: 10px; }
	.path-list li.active button { background: var(--accent-soft); color: var(--accent); }
	.path-list li.skipped { opacity: .5; text-decoration: line-through; }
	.inspector { min-width: 0; border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); padding: 24px; }
	.inspector-head, .section-head, .prepare { display: flex; align-items: start; justify-content: space-between; gap: 18px; }
	.inspector h2 { margin: 0; font: 500 27px Fraunces, Georgia, serif; }
	.inspector h3 { margin: 0; font-size: 16px; }
	.editor { display: grid; gap: 14px; margin-top: 24px; }
	label { display: grid; gap: 6px; color: var(--ink-2); font-size: 11px; font-weight: 600; }
	label small { color: var(--ink-3); font-weight: 400; }
	input, textarea, select { box-sizing: border-box; width: 100%; border: 1px solid var(--rule); border-radius: 6px; background: var(--paper); color: var(--ink); font-size: 13px; padding: 9px 10px; }
	textarea { min-height: 70px; resize: vertical; }
	.two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
	.editor > button { justify-self: start; }
	.dependencies { border-top: 1px solid var(--rule); margin-top: 24px; padding-top: 20px; }
	.dependencies ul { margin: 10px 0 0; padding-left: 17px; }
	.dependencies li { color: var(--ink-2); font-size: 12px; line-height: 1.6; }
	.dependencies p:last-child { color: var(--ink-2); font-size: 12px; }
	.shape, .prepare { border-top: 1px solid var(--rule); margin-top: 26px; padding-top: 22px; }
	.prepare { align-items: center; }
	.regenerate { display: grid; min-width: min(100%, 360px); gap: 8px; }
	.regenerate button { justify-self: end; }
	.prepare p:last-child { margin: 6px 0 0; color: var(--ink-2); font-size: 12px; }
	.ready-actions { display: flex; align-items: center; gap: 8px; }
	.empty { border: 1px dashed var(--rule); border-radius: 10px; padding: 54px 28px; text-align: center; }
	.empty h2 { margin: 0; font: 500 28px Fraunces, Georgia, serif; }
	.empty > p:last-of-type { max-width: 590px; margin: 12px auto 20px; color: var(--ink-2); font-size: 14px; line-height: 1.6; }
	.error { border: 1px solid #e2b9ae; border-radius: 7px; background: #f8e9e5; color: #873f30; margin-bottom: 18px; padding: 10px 12px; font-size: 13px; }
	.chat-edit { border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); margin-top: 22px; padding: 18px; }
	.chat-edit form { display: flex; gap: 8px; margin-top: 10px; }
	.chat-edit input { flex: 1; }
	.chat-note { margin: 10px 0 0; color: var(--ink-2); font-size: 12px; line-height: 1.5; }
	.chat-disabled { margin: 10px 0 0; color: var(--ink-3); font-size: 12px; }
	.confirm-backdrop { position: fixed; z-index: 50; inset: 0; display: grid; place-items: center; background: rgb(18 23 21 / .48); padding: 18px; }
	.confirm-dialog { width: min(100%, 470px); border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); box-shadow: 0 20px 60px rgb(0 0 0 / .18); padding: 22px; }
	.confirm-dialog h2 { margin: 0; font: 500 25px Fraunces, Georgia, serif; }
	.confirm-dialog > p:not(.eyebrow) { color: var(--ink-2); font-size: 13px; line-height: 1.5; }
	.confirm-dialog > div { display: flex; justify-content: end; gap: 8px; margin-top: 18px; }
	@media (max-width: 980px) { .status-board { grid-template-columns: repeat(4, 1fr); } }
	@media (max-width: 840px) { .workspace { grid-template-columns: 1fr; } .path-list { position: static; } .path-list ol { grid-template-columns: repeat(2, 1fr); } }
	@media (max-width: 640px) { .unit-page { padding: 28px 16px 60px; } .unit-head, .head-actions, .inspector-head, .section-head, .prepare, .lock-in-bar { align-items: stretch; flex-direction: column; } .lock-reason { text-align: left; } .history-panel .section-head > p { text-align: left; } .path-list ol, .two { grid-template-columns: 1fr; } .status-board { grid-template-columns: repeat(2, 1fr); } .inspector { padding: 18px; } .chat-edit form { flex-direction: column; } }
</style>
