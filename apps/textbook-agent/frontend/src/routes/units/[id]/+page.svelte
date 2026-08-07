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
		PathLesson,
		PathVersionSummary,
		PreparedLessonStatus,
		ResourceComposition,
		LessonShapePreview,
		TeachingSchedule,
		Unit,
		UnitGroups,
		UnitPath,
		MergeCriticResult
	} from '$lib/types/units';

	const unitId = $derived(page.params.id ?? '');
	let unit = $state<Unit | null>(null);
	let path = $state<UnitPath | null>(null);
	let selectedId = $state<string | null>(null);
	let loading = $state(true);
	let busy = $state<string | null>(null);
	let error = $state<string | null>(null);
	let tabError = $state<string | null>(null);
	let lessonMode = $state<LessonMode>('first_exposure');
	let shape = $state<LessonShapePreview | null>(null);
	let misconceptionCount = $state(1);
	let preparation = $state<PreparedLessonStatus | null>(null);
	let history = $state<PathVersionSummary[]>([]);
	let historyLoaded = $state(false);
	let viewedVersion = $state<UnitPath | null>(null);
	let schedule = $state<TeachingSchedule | null>(null);
	let scheduleLoaded = $state(false);
	let groups = $state<UnitGroups | null>(null);
	let groupsLoaded = $state(false);
	let compositions = $state<ResourceComposition[]>([]);
	let resourcesLoaded = $state(false);
	let selectedGroupIds = $state<string[]>([]);
	let activeView = $state<'path' | 'schedule' | 'groups' | 'results' | 'resources' | 'history'>('path');
	let restoreReason = $state('Restore this version as a new editable draft.');
	let pendingAction = $state<{ label: string; description: string; run: () => Promise<void> } | null>(null);
	let regenerationReason = $state('The lesson changed after preparation.');
	let editTitle = $state('');
	let editObjective = $state('');
	let editMustEstablish = $state('');
	let editExclusions = $state('');
	let chatMessage = $state('');
	let chatBusy = $state(false);
	let chatUnavailable = $state(false);
	let chatNote = $state<string | null>(null);
	let showVersions = $state(false);
	let showShapeDebug = $state(false);
	let dismissedSuggestions = $state<string[]>([]);
	const debugMode = import.meta.env.DEV;

	const mergeSuggestions = $derived(
		(path?.merge_critic_results ?? []).filter((row) => row.source === 'deterministic')
	);

	const selected = $derived(path?.lessons.find((lesson) => lesson.id === selectedId) ?? null);
	const canLockIn = $derived(Boolean(path && path.lessons.length > 0 && path.status !== 'approved'));
	const planningFailed = $derived(Boolean(unit && !unit.active_path_version_id && !path));

	function lines(value: string): string[] {
		return value.split('\n').map((item) => item.trim()).filter(Boolean);
	}

	function plannerInput(current: Unit) {
		return {
			topic: current.topic,
			subject: current.subject,
			grade_level: current.grade_level,
			destination_objective: current.destination_objective,
			starting_knowledge: current.starting_knowledge,
			curriculum_context: current.curriculum_context,
			class_notes: current.class_notes
		};
	}

	function dependencySentences(lesson: PathLesson | null): string[] {
		if (!lesson || !path) return [];
		const sentences: string[] = [];
		for (const prerequisiteId of lesson.prerequisites) {
			const prerequisite = path.lessons.find((candidate) => candidate.id === prerequisiteId);
			if (prerequisite) sentences.push(`needs lesson ${prerequisite.position + 1}`);
		}
		return sentences;
	}

	function fillEditor(lesson: PathLesson): void {
		editTitle = lesson.title;
		editObjective = lesson.objective;
		editMustEstablish = lesson.must_establish.join('\n');
		editExclusions = lesson.exclusions.join('\n');
	}

	function selectLesson(lesson: PathLesson): void {
		selectedId = lesson.id;
		fillEditor(lesson);
		shape = null;
		preparation = null;
		showShapeDebug = false;
	}

	function suggestionKey(row: MergeCriticResult): string {
		return `${row.lesson_a}:${row.lesson_b}`;
	}

	async function mergeSuggested(row: MergeCriticResult): Promise<void> {
		if (!path) return;
		const lessonA = path.lessons.find((lesson) => lesson.id === row.lesson_a);
		const lessonB = path.lessons.find((lesson) => lesson.id === row.lesson_b);
		if (!lessonA || !lessonB) return;
		await act('merge-suggestion', async () => {
			const result = await mergePathLessons(
				unitId,
				path as UnitPath,
				[lessonA, lessonB],
				[lessonA.id, lessonB.id],
				{
					title: `${lessonA.title} and ${lessonB.title}`,
					objective: lessonA.objective,
					must_establish: [...new Set([...lessonA.must_establish, ...lessonB.must_establish])],
					knowledge_type: lessonA.primary_knowledge_type
				}
			);
			path = result.path;
			dismissedSuggestions = [...dismissedSuggestions, suggestionKey(row)];
			if (path.lessons[0]) selectLesson(path.lessons[0]);
		});
	}

	async function ensurePreparationStatus(): Promise<void> {
		if (!selected) return;
		try {
			preparation = await getPreparedLessonStatus(unitId, selected.id);
		} catch (err) {
			preparation = null;
			error = err instanceof Error ? err.message : 'Could not load preparation status.';
		}
	}

	async function ensureShape(): Promise<void> {
		if (!selected) return;
		try {
			shape = await getLessonShape(unitId, selected.id, lessonMode, misconceptionCount);
		} catch (err) {
			shape = null;
			error = err instanceof Error ? err.message : 'Could not load this lesson shape.';
		}
	}

	async function updateShapeSettings(mode: LessonMode, count: number): Promise<void> {
		if (!selected) return;
		lessonMode = mode;
		misconceptionCount = count;
		shape = null;
		await ensureShape();
	}

	async function updateShapeRevision(revision: number): Promise<void> {
		if (!selected) return;
		selected.revision = revision;
		await ensurePreparationStatus();
	}

	async function load(options: { preserveSelection?: boolean } = {}): Promise<void> {
		loading = true;
		error = null;
		try {
			unit = await getUnit(unitId);
			if (unit.active_path_version_id) {
				path = await getUnitPath(unitId);
			} else {
				path = null;
			}
			if (path?.lessons.length) {
				const target = options.preserveSelection
					? path.lessons.find((lesson) => lesson.id === selectedId) ?? path.lessons[0]
					: path.lessons[0];
				selectLesson(target);
			} else {
				selectedId = null;
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load the unit workspace.';
		} finally {
			loading = false;
		}
	}

	async function openTab(view: typeof activeView): Promise<void> {
		activeView = view;
		tabError = null;
		if (!unit) return;
		try {
			if (view === 'groups' && !groupsLoaded) {
				groups = await getUnitGroups(unitId);
				selectedGroupIds = groups.groups.map((group) => group.id);
				groupsLoaded = true;
			} else if (view === 'schedule' && !scheduleLoaded) {
				schedule = await getTeachingSchedule(unitId);
				scheduleLoaded = true;
			} else if (view === 'resources' && !resourcesLoaded) {
				if (!groupsLoaded) {
					groups = await getUnitGroups(unitId);
					selectedGroupIds = groups.groups.map((group) => group.id);
					groupsLoaded = true;
				}
				if (!scheduleLoaded) {
					schedule = await getTeachingSchedule(unitId);
					scheduleLoaded = true;
				}
				compositions = await listUnitResources(unitId);
				resourcesLoaded = true;
			} else if (view === 'history' && !historyLoaded) {
				history = await getPathHistory(unitId);
				historyLoaded = true;
			} else if (view === 'results' && !groupsLoaded) {
				groups = await getUnitGroups(unitId);
				selectedGroupIds = groups.groups.map((group) => group.id);
				groupsLoaded = true;
			}
		} catch (err) {
			tabError = err instanceof Error ? err.message : 'Could not load this tab.';
		}
	}

	async function act(label: string, action: () => Promise<unknown>, reload = true): Promise<void> {
		busy = label;
		error = null;
		try {
			await action();
			if (reload) await load({ preserveSelection: true });
		} catch (err) {
			const message = err instanceof Error ? err.message : 'That change did not go through.';
			error = message;
			if (isApiError(err) && err.status === 409) {
				await load({ preserveSelection: true });
				error = message;
			}
		} finally {
			busy = null;
		}
	}

	async function planOrReplan(replan: boolean): Promise<void> {
		if (!unit) return;
		await act(replan ? 'replan' : 'plan', async () => {
			path = await planUnitPath(unitId, plannerInput(unit as Unit), replan, path ?? undefined);
			unit = await getUnit(unitId);
			historyLoaded = false;
			if (path.lessons.length) selectLesson(path.lessons[0]);
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
			if (!groupsLoaded) {
				try {
					groups = await getUnitGroups(unitId);
					selectedGroupIds = groups.groups.map((group) => group.id);
					groupsLoaded = true;
				} catch {
					selectedGroupIds = [];
				}
			}
			await ensureShape();
			const prepared = await preparePathLesson(
				unitId,
				path as UnitPath,
				selected,
				lessonMode,
				selectedGroupIds
			);
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
		tabError = null;
		try { viewedVersion = await getHistoricalPath(unitId, version.id); }
		catch (err) { tabError = err instanceof Error ? err.message : 'Could not load path history.'; }
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
			<section class="empty">
				{#if planningFailed}
					<p class="eyebrow">Planning did not finish</p>
					<h2>This unit is saved as a draft</h2>
					<p>Lesson planning did not complete. Nothing else was corrupted — try planning again on this same unit.</p>
					<button class="primary" type="button" disabled={busy !== null} onclick={() => planOrReplan(false)}>{busy === 'plan' ? 'Planning your lessons…' : 'Try planning again'}</button>
				{:else}
					<p class="eyebrow">Destination saved</p>
					<h2>Build your lessons</h2>
					<p>This turns your destination into a numbered list of lessons.</p>
					<button class="primary" type="button" disabled={busy !== null} onclick={() => planOrReplan(false)}>{busy === 'plan' ? 'Planning your lessons…' : 'Plan the lessons'}</button>
				{/if}
			</section>
		{:else}
			<nav class="view-tabs" aria-label="Unit workspace views">
				<button type="button" class:active={activeView === 'path'} aria-current={activeView === 'path' ? 'page' : undefined} onclick={() => openTab('path')}>Lessons</button>
				<button type="button" class:active={activeView === 'schedule'} aria-current={activeView === 'schedule' ? 'page' : undefined} onclick={() => openTab('schedule')}>Schedule</button>
				<button type="button" class:active={activeView === 'groups'} aria-current={activeView === 'groups' ? 'page' : undefined} onclick={() => openTab('groups')}>Groups</button>
				<button type="button" class:active={activeView === 'resources'} aria-current={activeView === 'resources' ? 'page' : undefined} onclick={() => openTab('resources')}>Resources</button>
				<button type="button" class:active={activeView === 'results'} aria-current={activeView === 'results' ? 'page' : undefined} onclick={() => openTab('results')}>Results</button>
				<button type="button" class:active={activeView === 'history'} aria-current={activeView === 'history' ? 'page' : undefined} onclick={() => openTab('history')}>History</button>
			</nav>
			{#if tabError && activeView !== 'path'}
				<p class="error" role="alert">{tabError}</p>
			{/if}
			{#if activeView === 'path'}
			{#if mergeSuggestions.some((row) => !dismissedSuggestions.includes(suggestionKey(row)))}
				<section class="suggestions" aria-label="Lesson suggestions">
					<p class="eyebrow">Suggestions</p>
					<ul>
						{#each mergeSuggestions as row (suggestionKey(row))}
							{#if !dismissedSuggestions.includes(suggestionKey(row))}
								<li>
									<p>{row.reason}</p>
									<div class="suggestion-actions">
										<button type="button" disabled={busy !== null} onclick={() => mergeSuggested(row)}>Merge these</button>
										<button type="button" class="ghost" disabled={busy !== null} onclick={() => { dismissedSuggestions = [...dismissedSuggestions, suggestionKey(row)]; }}>Dismiss</button>
									</div>
								</li>
							{/if}
						{/each}
					</ul>
				</section>
			{/if}
			<section class="lock-in-bar">
				<p>{path.lessons.length} {path.lessons.length === 1 ? 'lesson' : 'lessons'}</p>
				{#if path.status !== 'approved'}
					<div class="lock-in">
						<button class="primary" type="button" disabled={busy !== null || !canLockIn} onclick={() => act('approve', async () => { path = await approveUnitPath(unitId, path as UnitPath); unit = await getUnit(unitId); }, false)}>{busy === 'approve' ? 'Locking it in…' : 'Looks good — lock it in'}</button>
					</div>
				{/if}
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
							<label><span>Must establish <small>one per line</small></span><textarea bind:value={editMustEstablish} required></textarea></label>
							<button class="secondary" type="submit" disabled={busy !== null}>{busy === 'save' ? 'Saving…' : 'Save lesson changes'}</button>
						</form>

						<section class="dependencies"><div><p class="eyebrow">Before this lesson</p><h3>What earlier lessons it requires</h3></div>{#if dependencySentences(selected).length}<ul>{#each dependencySentences(selected) as sentence}<li>{sentence}</li>{/each}</ul>{:else}<p>Nothing — this can be the starting point.</p>{/if}</section>

						{#if debugMode}
							<section class="shape">
								{#if !showShapeDebug}
									<button class="text-button" type="button" onclick={() => { showShapeDebug = true; void ensureShape(); }}>Show shape debug</button>
								{:else if shape}
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
									<p>Loading this lesson's shape…</p>
								{/if}
							</section>
						{/if}

						<section class="prepare">
							<div>
								<p class="eyebrow">Preparation</p>
								<h3>{preparation?.workflow_stage ?? 'Ready when you are'}</h3>
								<p>{preparation?.stale ? 'This lesson changed since it was last written and needs to be made again.' : 'Prepare uses the approved lesson path and the existing page-oriented generation flow.'}</p>
							</div>
							{#if preparation?.stale && preparation.can_regenerate}
								<form class="regenerate" onsubmit={(event) => { event.preventDefault(); void regenerate(); }}>
									<label><span>What changed</span><input bind:value={regenerationReason} minlength="3" maxlength="500" required /></label>
									<button class="primary" type="submit" disabled={busy !== null || regenerationReason.trim().length < 3}>{busy === 'regenerate' ? 'Making it again…' : 'Make it again'}</button>
								</form>
							{:else if preparation?.generation_id}
								<div class="ready-actions">
									<a class="primary link" href={`/studio?generation_id=${encodeURIComponent(preparation.generation_id)}`}>Open review</a>
									<a class="secondary link" href={`/studio/print/${encodeURIComponent(preparation.generation_id)}`}>Print</a>
									<button class="secondary" type="button" onclick={() => { void openTab('groups'); showVersions = true; }}>Make versions for my groups</button>
									<button class="text-button" type="button" disabled={busy !== null} onclick={() => ensurePreparationStatus()}>Refresh status</button>
								</div>
							{:else}
								<div class="ready-actions">
									<button class="primary" type="button" disabled={path.status !== 'approved' || selected.skipped || busy !== null} onclick={prepare}>{busy === 'prepare' ? 'Making the lesson…' : 'Prepare Lesson'}</button>
									<button class="text-button" type="button" disabled={busy !== null} onclick={() => ensurePreparationStatus()}>Check preparation status</button>
								</div>
							{/if}
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
			{:else if activeView === 'schedule'}
				{#if schedule}
					<TeachingSchedulePanel {unitId} {path} {schedule} onsaved={(saved) => (schedule = saved)} />
				{:else if !tabError}
					<p class="loading" role="status">Loading schedule…</p>
				{/if}
			{:else if activeView === 'groups'}
				{#if groups}
					<UnitGroupsPanel {unitId} {groups} onsaved={(saved) => { groups = saved; selectedGroupIds = saved.groups.map((group) => group.id); }} />
				{:else if !tabError}
					<p class="loading" role="status">Loading groups…</p>
				{/if}
			{:else if activeView === 'results'}
				{#if groups}
					<LessonResultsPanel {unitId} {path} lessons={path.lessons} {groups} />
				{:else if !tabError}
					<p class="loading" role="status">Loading results…</p>
				{/if}
			{:else if activeView === 'resources'}
				{#if groups && schedule}
					<ResourceComposerPanel {unitId} {path} lessons={path.lessons} {groups} {schedule} {compositions} oncreated={(created) => (compositions = [created, ...compositions])} />
				{:else if !tabError}
					<p class="loading" role="status">Loading resources…</p>
				{/if}
			{:else if activeView === 'history'}
				<section class="history-panel">
					<div class="section-head"><div><p class="eyebrow">Lesson history</p><h2>Recoverable versions</h2></div><p>Structural edits create a new draft. Older routes remain available.</p></div>
					{#if historyLoaded}
						<div class="history-list">{#each history as version}<article class:current={version.id === path.id}><div><strong>v{version.version}</strong><span>{version.status}</span><small>{version.generated_by}</small></div><div class="history-actions"><button type="button" class="text-button" onclick={() => viewVersion(version)}>Inspect</button>{#if version.id !== path.id}<button type="button" class="text-button" onclick={() => confirmRestore(version)}>Restore</button>{/if}</div></article>{/each}</div>
						{#if viewedVersion}<div class="history-preview"><div><strong>v{viewedVersion.version}</strong><span>{viewedVersion.status} · {viewedVersion.lessons.length} lessons</span></div><ol>{#each viewedVersion.lessons as lesson}<li>{lesson.title}</li>{/each}</ol><button type="button" class="text-button" onclick={() => (viewedVersion = null)}>Close preview</button></div>{/if}
					{:else if !tabError}
						<p class="loading" role="status">Loading history…</p>
					{/if}
				</section>
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
	.unit-head, .view-tabs, .lock-in-bar, .history-panel, .workspace, .chat-edit, .empty, .error, .loading { max-width: 1180px; margin-inline: auto; }
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
	.suggestions { max-width: 1180px; margin: 0 auto 18px; border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); padding: 16px 18px; }
	.suggestions ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }
	.suggestions li { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
	.suggestions p { margin: 0; color: var(--ink-2); font-size: 13px; }
	.suggestion-actions { display: flex; gap: 8px; flex-shrink: 0; }
	.suggestion-actions .ghost { background: transparent; border: 1px solid var(--rule); color: var(--ink-2); }
	.lock-in-bar p { margin: 0; color: var(--ink-2); font-size: 13px; }
	.lock-in { display: grid; justify-items: end; gap: 6px; }
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
	@media (max-width: 840px) { .workspace { grid-template-columns: 1fr; } .path-list { position: static; } .path-list ol { grid-template-columns: repeat(2, 1fr); } }
	@media (max-width: 640px) { .unit-page { padding: 28px 16px 60px; } .unit-head, .head-actions, .inspector-head, .section-head, .prepare, .lock-in-bar { align-items: stretch; flex-direction: column; } .history-panel .section-head > p { text-align: left; } .path-list ol, .two { grid-template-columns: 1fr; } .inspector { padding: 18px; } .chat-edit form { flex-direction: column; } }
</style>
