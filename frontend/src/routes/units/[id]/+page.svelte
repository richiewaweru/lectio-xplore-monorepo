<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import {
		approveUnitPath,
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
		reorderPathLessons,
		restorePathVersion,
		skipPathLesson,
		splitPathLesson
	} from '$lib/api/units';
	import TeachingSchedulePanel from '$lib/components/units/TeachingSchedulePanel.svelte';
	import UnitGroupsPanel from '$lib/components/units/UnitGroupsPanel.svelte';
	import LessonShapePanel from '$lib/components/units/LessonShapePanel.svelte';
	import LessonResultsPanel from '$lib/components/units/LessonResultsPanel.svelte';
	import ResourceComposerPanel from '$lib/components/units/ResourceComposerPanel.svelte';
	import type {
		KnowledgeType,
		LessonMode,
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
	let regenerationReason = $state('The path lesson changed after preparation.');
	let editTitle = $state('');
	let editObjective = $state('');
	let editMustEstablish = $state('');
	let editExclusions = $state('');
	let editType = $state<KnowledgeType>('conceptual');
	let showSplit = $state(false);
	let splitATitle = $state('');
	let splitAObjective = $state('');
	let splitBTitle = $state('');
	let splitBObjective = $state('');
	let showMerge = $state(false);
	let mergeTitle = $state('');
	let mergeObjective = $state('');

	const selected = $derived(path?.lessons.find((lesson) => lesson.id === selectedId) ?? null);
	const selectedIndex = $derived(path && selected ? path.lessons.findIndex((lesson) => lesson.id === selected.id) : -1);
	const nextLesson = $derived(path && selectedIndex >= 0 ? path.lessons[selectedIndex + 1] ?? null : null);

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

	function fillEditor(lesson: PathLesson): void {
		editTitle = lesson.title;
		editObjective = lesson.objective;
		editMustEstablish = lesson.must_establish.join('\n');
		editExclusions = lesson.exclusions.join('\n');
		editType = lesson.primary_knowledge_type;
		splitATitle = `${lesson.title} — foundation`;
		splitAObjective = lesson.objective;
		splitBTitle = `${lesson.title} — application`;
		splitBObjective = lesson.objective;
		mergeTitle = nextLesson ? `${lesson.title} and ${nextLesson.title}` : lesson.title;
		mergeObjective = nextLesson ? `${lesson.objective} ${nextLesson.objective}` : lesson.objective;
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
			error = err instanceof Error ? err.message : 'Could not load the controlled lesson shape.';
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
			error = err instanceof Error ? err.message : 'The unit action failed.';
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
			must_establish: lines(editMustEstablish), exclusions: lines(editExclusions),
			primary_knowledge_type: editType
		}));
	}

	function move(offset: number): void {
		if (!path || selectedIndex < 0) return;
		const target = selectedIndex + offset;
		if (target < 0 || target >= path.lessons.length) return;
		const ids = path.lessons.map((lesson) => lesson.id);
		[ids[selectedIndex], ids[target]] = [ids[target], ids[selectedIndex]];
		pendingAction = {
			label: `Move ${selected?.title ?? 'lesson'}`,
			description: 'This creates a new draft path version. The current version stays in history for recovery.',
			run: () => act('reorder', () => reorderPathLessons(unitId, path as UnitPath, ids))
		};
	}

	async function splitSelected(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (!selected) return;
		await act('split', () => splitPathLesson(unitId, path as UnitPath, selected, [
			{ concept_candidate: { slug: slug(splitATitle), title: splitATitle.trim() }, objective: splitAObjective.trim(), must_establish: [splitAObjective.trim()], exclusions: selected.exclusions, primary_knowledge_type: selected.primary_knowledge_type, secondary_demand: selected.secondary_demand },
			{ concept_candidate: { slug: slug(splitBTitle), title: splitBTitle.trim() }, objective: splitBObjective.trim(), must_establish: [splitBObjective.trim()], exclusions: selected.exclusions, primary_knowledge_type: selected.primary_knowledge_type, secondary_demand: selected.secondary_demand }
		]));
		showSplit = false;
	}

	async function mergeSelected(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (!selected || !nextLesson) return;
		await act('merge', () => mergePathLessons(unitId, path as UnitPath, [selected, nextLesson], [selected.id, nextLesson.id], {
			concept_candidate: { slug: slug(mergeTitle), title: mergeTitle.trim() },
			objective: mergeObjective.trim(),
			must_establish: [...selected.must_establish, ...nextLesson.must_establish],
			exclusions: [...new Set([...selected.exclusions, ...nextLesson.exclusions])],
			primary_knowledge_type: selected.primary_knowledge_type,
			secondary_demand: selected.secondary_demand
		}));
		showMerge = false;
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
				{#if path}<span class:approved={path.status === 'approved'}>Path v{path.version} · {path.status}</span>{/if}
				<button class="secondary" type="button" disabled={busy !== null} onclick={() => planOrReplan(Boolean(path))}>{busy === 'replan' || busy === 'plan' ? 'Planning…' : path ? 'Replan path' : 'Plan concept path'}</button>
			</div>
		</header>

		{#if error}<p class="error" role="alert">{error}</p>{/if}

		{#if !path}
			<section class="empty"><p class="eyebrow">Destination saved</p><h2>Build the concept route</h2><p>The planner works backward from the destination and verifies every prerequisite forward. It receives no lesson-count or duration target.</p><button class="primary" type="button" disabled={busy !== null} onclick={() => planOrReplan(false)}>{busy === 'plan' ? 'Planning the route…' : 'Plan concept path'}</button></section>
		{:else}
			<nav class="view-tabs" aria-label="Unit workspace views">
				<button type="button" class:active={activeView === 'path'} aria-current={activeView === 'path' ? 'page' : undefined} onclick={() => (activeView = 'path')}>Concept path</button>
				<button type="button" class:active={activeView === 'schedule'} aria-current={activeView === 'schedule' ? 'page' : undefined} onclick={() => (activeView = 'schedule')}>Schedule <span>{schedule?.periods.length ?? 0}</span></button>
				<button type="button" class:active={activeView === 'groups'} aria-current={activeView === 'groups' ? 'page' : undefined} onclick={() => (activeView = 'groups')}>Groups <span>{groups?.groups.length ?? 0}</span></button>
				<button type="button" class:active={activeView === 'results'} aria-current={activeView === 'results' ? 'page' : undefined} onclick={() => (activeView = 'results')}>Results</button>
				<button type="button" class:active={activeView === 'resources'} aria-current={activeView === 'resources' ? 'page' : undefined} onclick={() => (activeView = 'resources')}>Resources <span>{compositions.length}</span></button>
			</nav>
			{#if activeView === 'path'}
			<section class="path-summary">
				<div><strong>{path.lessons.length}</strong><span>capabilities</span></div><div><strong>{path.forward_verified ? 'Yes' : 'No'}</strong><span>forward verified</span></div><div><strong>{path.reaches_destination ? 'Yes' : 'No'}</strong><span>destination reached</span></div><div><strong>{path.prerequisite_risks.length}</strong><span>prerequisite risks</span></div>
				{#if path.status !== 'approved'}<button class="primary" type="button" disabled={busy !== null || !path.reaches_destination || path.prerequisite_risks.length > 0} onclick={() => act('approve', async () => { path = await approveUnitPath(unitId, path as UnitPath); unit = await getUnit(unitId); await load({ preserveSelection: true }); }, false)}>{busy === 'approve' ? 'Approving…' : 'Approve path'}</button>{/if}
			</section>

			{#if aggregate}
				<section class="status-board" aria-label="Lesson preparation status">
					{#each Object.entries(aggregate.counts) as [state, count]}
						<div class:attention={state === 'failed' || state === 'stale' || state === 'warning'}><strong>{count}</strong><span>{state.replace('_', ' ')}</span></div>
					{/each}
				</section>
			{/if}

			<section class="path-health">
				<div><p class="eyebrow">Completeness</p><h3>{path.forward_verified && path.reaches_destination ? 'Route verified' : 'Needs attention'}</h3><p>{path.completeness_note ?? 'Every prerequisite must resolve before the destination can be approved.'}</p></div>
				<div><p class="eyebrow">Prerequisite risks</p><h3>{path.prerequisite_risks.length}</h3>{#if path.prerequisite_risks.length}<ul>{#each path.prerequisite_risks as risk}<li>{String(risk.note ?? risk.missing ?? 'Unresolved prerequisite')}</li>{/each}</ul>{:else}<p>No unresolved prerequisite risks.</p>{/if}</div>
			</section>

			<section class="history-panel">
				<div class="section-head"><div><p class="eyebrow">Path history</p><h2>Recoverable versions</h2></div><p>Structural edits create a new draft. Older routes remain available.</p></div>
				<div class="history-list">{#each history as version}<article class:current={version.id === path.id}><div><strong>v{version.version}</strong><span>{version.status}</span><small>{version.generated_by}</small></div><div class="history-actions"><button type="button" class="text-button" onclick={() => viewVersion(version)}>Inspect</button>{#if version.id !== path.id}<button type="button" class="text-button" onclick={() => confirmRestore(version)}>Restore</button>{/if}</div></article>{/each}</div>
				{#if viewedVersion}<div class="history-preview"><div><strong>Path v{viewedVersion.version}</strong><span>{viewedVersion.status} · {viewedVersion.lessons.length} capabilities</span></div><ol>{#each viewedVersion.lessons as lesson}<li>{lesson.title}</li>{/each}</ol><button type="button" class="text-button" onclick={() => (viewedVersion = null)}>Close preview</button></div>{/if}
			</section>

			<div class="workspace">
				<aside class="path-list" aria-label="Concept path">
					<p class="eyebrow">Concept path</p>
					<ol>{#each path.lessons as lesson, index (lesson.id)}<li class:active={lesson.id === selectedId} class:skipped={lesson.skipped}><button type="button" onclick={() => selectLesson(lesson)}><span>{index + 1}</span><span><strong>{lesson.title}</strong><small>{lesson.primary_knowledge_type}{lesson.pack_id ? ' · prepared' : ''}</small></span></button></li>{/each}</ol>
				</aside>

				{#if selected}
					<main class="inspector">
						<div class="inspector-head"><div><p class="eyebrow">Capability {selected.position + 1}</p><h2>{selected.title}</h2></div><div class="compact-actions"><button type="button" aria-label="Move lesson up" disabled={selectedIndex <= 0 || busy !== null} onclick={() => move(-1)}>↑</button><button type="button" aria-label="Move lesson down" disabled={selectedIndex >= path.lessons.length - 1 || busy !== null} onclick={() => move(1)}>↓</button><button type="button" disabled={selected.skipped || busy !== null} onclick={() => (pendingAction = { label: `Skip ${selected.title}`, description: 'This creates a new draft path version and keeps the current route available for undo.', run: () => act('skip', () => skipPathLesson(unitId, path as UnitPath, selected)) })}>Skip</button></div></div>

						<form class="editor" onsubmit={saveLesson}>
							<label><span>Title</span><input bind:value={editTitle} required /></label>
							<label><span>Objective <small>owned by this path lesson</small></span><textarea bind:value={editObjective} required></textarea></label>
							<div class="two"><label><span>Must establish <small>one per line</small></span><textarea bind:value={editMustEstablish} required></textarea></label><label><span>Exclusions <small>one per line</small></span><textarea bind:value={editExclusions}></textarea></label></div>
							<label><span>Knowledge type</span><select bind:value={editType}><option value="factual">Factual</option><option value="conceptual">Conceptual</option><option value="procedural">Procedural</option><option value="evaluative">Evaluative</option></select></label>
							<button class="secondary" type="submit" disabled={busy !== null}>{busy === 'save' ? 'Saving…' : 'Save lesson changes'}</button>
						</form>

						<section class="dependencies"><div><p class="eyebrow">Prerequisites</p><h3>What this capability depends on</h3></div><div class="dependency-grid"><div><strong>Earlier path capabilities</strong>{#if selected.prerequisites.length}<ul>{#each selected.prerequisites as prerequisiteId}<li>{path.lessons.find((lesson) => lesson.id === prerequisiteId)?.title ?? prerequisiteId}</li>{/each}</ul>{:else}<p>None inside this path.</p>{/if}</div><div><strong>External starting knowledge</strong>{#if selected.external_prerequisites.length}<ul>{#each selected.external_prerequisites as prerequisite}<li>{prerequisite}</li>{/each}</ul>{:else}<p>None declared.</p>{/if}</div></div></section>

						<div class="structure-actions"><button type="button" class="text-button" onclick={() => (showSplit = !showSplit)}>Split lesson</button><button type="button" class="text-button" disabled={!nextLesson} onclick={() => (showMerge = !showMerge)}>Merge with next</button></div>
						{#if showSplit}<form class="operation-form" onsubmit={splitSelected}><h3>Split into two capabilities</h3><label><span>First title</span><input bind:value={splitATitle} required /></label><label><span>First objective</span><textarea bind:value={splitAObjective} required></textarea></label><label><span>Second title</span><input bind:value={splitBTitle} required /></label><label><span>Second objective</span><textarea bind:value={splitBObjective} required></textarea></label><button class="secondary" type="submit" disabled={busy !== null}>{busy === 'split' ? 'Splitting…' : 'Confirm split'}</button></form>{/if}
						{#if showMerge && nextLesson}<form class="operation-form" onsubmit={mergeSelected}><h3>Merge with {nextLesson.title}</h3><label><span>Merged title</span><input bind:value={mergeTitle} required /></label><label><span>Merged objective</span><textarea bind:value={mergeObjective} required></textarea></label><button class="secondary" type="submit" disabled={busy !== null}>{busy === 'merge' ? 'Merging…' : 'Confirm merge'}</button></form>{/if}

						{#if shape}
							<LessonShapePanel
								{unitId}
								{path}
								lesson={selected}
								{shape}
								{lessonMode}
								{misconceptionCount}
								onsettings={updateShapeSettings}
								onshape={(value) => (shape = value)}
								onrevision={updateShapeRevision}
							/>
						{:else}
							<section class="shape"><p>Loading controlled lesson shape…</p></section>
						{/if}

						<section class="prepare">
							<div><p class="eyebrow">Preparation</p><h3>{preparation?.workflow_stage ?? 'Checking status…'}</h3><p>{preparation?.stale ? 'The existing preparation is stale and must be regenerated.' : 'Preparation enters the durable concept-card review before lesson writing.'}</p></div>
							{#if groups?.groups.length}
								<fieldset class="prepare-groups"><legend>Booklet groups</legend>{#each groups.groups as group}<label><input type="checkbox" value={group.id} bind:group={selectedGroupIds} /><span>{group.label} <small>{group.profile}</small></span></label>{/each}<p>All selected booklets use one shared diagnostic item set.</p></fieldset>
							{/if}
							{#if preparation?.stale && preparation.can_regenerate}
								<form class="regenerate" onsubmit={(event) => { event.preventDefault(); void regenerate(); }}>
									<label><span>Regeneration reason</span><input bind:value={regenerationReason} minlength="3" maxlength="500" required /></label>
									<button class="primary" type="submit" disabled={busy !== null || !shape?.can_prepare || regenerationReason.trim().length < 3}>{busy === 'regenerate' ? 'Regenerating…' : 'Regenerate preparation'}</button>
								</form>
							{:else if preparation?.generation_id}<a class="primary link" href={`/studio?generation_id=${encodeURIComponent(preparation.generation_id)}`}>Open review</a>{:else}<button class="primary" type="button" disabled={path.status !== 'approved' || selected.skipped || busy !== null || !shape?.can_prepare} onclick={prepare}>{busy === 'prepare' ? 'Preparing…' : 'Prepare lesson'}</button>{/if}
						</section>
					</main>
				{/if}
			</div>
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
	.unit-head, .view-tabs, .path-summary, .status-board, .path-health, .history-panel, .workspace, .empty, .error, .loading { max-width: 1180px; margin-inline: auto; }
	.unit-head { display: flex; align-items: end; justify-content: space-between; gap: 24px; margin-bottom: 28px; }
	.back { display: inline-block; margin-bottom: 18px; color: var(--accent); font-size: 13px; font-weight: 600; text-decoration: none; }
	.eyebrow { margin: 0 0 6px; color: var(--ink-3); font: 500 10px 'IBM Plex Mono', monospace; letter-spacing: .1em; text-transform: uppercase; }
	h1 { margin: 0; font: 500 36px/1.1 Fraunces, Georgia, serif; letter-spacing: -.03em; }
	.unit-head p:last-child { max-width: 720px; margin: 9px 0 0; color: var(--ink-2); font-size: 14px; line-height: 1.5; }
	.head-actions { display: flex; align-items: center; gap: 10px; }
	.head-actions > span { border-radius: 999px; background: var(--amber-soft); color: var(--amber); font: 500 10px 'IBM Plex Mono', monospace; padding: 6px 9px; text-transform: uppercase; }
	.head-actions > span.approved { background: var(--accent-soft); color: var(--accent); }
	button, input, textarea, select { font: inherit; }
	.primary, .secondary, .text-button, .compact-actions button { cursor: pointer; }
	.primary, .secondary { border-radius: 7px; font-size: 13px; font-weight: 600; padding: 9px 13px; }
	.primary { border: 1px solid var(--accent); background: var(--accent); color: white; }
	.primary.link { display: inline-block; text-decoration: none; }
	.secondary { border: 1px solid var(--rule); background: var(--surface); color: var(--ink); }
	button:disabled { cursor: not-allowed; opacity: .45; }
	.view-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--rule); margin-bottom: 22px; }
	.view-tabs button { border: 0; border-bottom: 2px solid transparent; background: transparent; color: var(--ink-3); cursor: pointer; padding: 10px 13px; font-size: 12px; font-weight: 600; }
	.view-tabs button.active { border-bottom-color: var(--accent); color: var(--accent); }
	.view-tabs span { display: inline-grid; place-items: center; min-width: 17px; height: 17px; border-radius: 999px; background: var(--paper); margin-left: 4px; font-size: 9px; }
	.path-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)) auto; align-items: center; gap: 16px; border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); margin-bottom: 22px; padding: 16px 18px; }
	.path-summary div { display: grid; gap: 2px; }
	.path-summary strong { font: 500 20px Fraunces, Georgia, serif; }
	.path-summary span { color: var(--ink-3); font-size: 11px; }
	.status-board { display: grid; grid-template-columns: repeat(8, minmax(0, 1fr)); gap: 6px; margin-bottom: 14px; }
	.status-board div { display: grid; gap: 2px; border: 1px solid var(--rule); border-radius: 7px; background: var(--surface); padding: 9px 10px; }
	.status-board div.attention { border-color: #dfb294; background: #fff7ed; }
	.status-board strong { font: 500 18px Fraunces, Georgia, serif; }
	.status-board span { color: var(--ink-3); font-size: 9px; text-transform: uppercase; }
	.path-health { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 16px; }
	.path-health > div { border: 1px solid var(--rule); border-radius: 8px; background: var(--surface); padding: 15px; }
	.path-health h3 { margin: 0; font-size: 15px; }
	.path-health p:last-child, .path-health li { color: var(--ink-2); font-size: 11px; line-height: 1.5; }
	.path-health ul { margin: 8px 0 0; padding-left: 17px; }
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
	.path-list li button small { margin-top: 3px; color: var(--ink-3); font-size: 10px; text-transform: capitalize; }
	.path-list li.active button { background: var(--accent-soft); color: var(--accent); }
	.path-list li.skipped { opacity: .5; text-decoration: line-through; }
	.inspector { min-width: 0; border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); padding: 24px; }
	.inspector-head, .section-head, .prepare { display: flex; align-items: start; justify-content: space-between; gap: 18px; }
	.inspector h2 { margin: 0; font: 500 27px Fraunces, Georgia, serif; }
	.inspector h3 { margin: 0; font-size: 16px; }
	.compact-actions { display: flex; gap: 4px; }
	.compact-actions button, .text-button { border: 1px solid var(--rule); border-radius: 6px; background: var(--paper); color: var(--ink-2); font-size: 12px; padding: 6px 9px; }
	.editor, .operation-form { display: grid; gap: 14px; margin-top: 24px; }
	label { display: grid; gap: 6px; color: var(--ink-2); font-size: 11px; font-weight: 600; }
	label small { color: var(--ink-3); font-weight: 400; }
	input, textarea, select { box-sizing: border-box; width: 100%; border: 1px solid var(--rule); border-radius: 6px; background: var(--paper); color: var(--ink); font-size: 13px; padding: 9px 10px; }
	textarea { min-height: 70px; resize: vertical; }
	.two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
	.editor > button { justify-self: start; }
	.structure-actions { display: flex; gap: 8px; margin-top: 14px; }
	.dependencies { border-top: 1px solid var(--rule); margin-top: 24px; padding-top: 20px; }
	.dependency-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 12px; }
	.dependency-grid > div { border: 1px solid var(--rule); border-radius: 7px; background: var(--paper); padding: 12px; }
	.dependency-grid strong { font-size: 11px; }
	.dependency-grid p, .dependency-grid li { color: var(--ink-2); font-size: 11px; }
	.dependency-grid ul { margin: 8px 0 0; padding-left: 17px; }
	.operation-form { border: 1px solid var(--rule); border-radius: 8px; background: var(--paper); padding: 16px; }
	.operation-form > button { justify-self: start; }
	.shape, .prepare { border-top: 1px solid var(--rule); margin-top: 26px; padding-top: 22px; }
	.prepare { align-items: center; }
	.regenerate { display: grid; min-width: min(100%, 360px); gap: 8px; }
	.regenerate button { justify-self: end; }
	.prepare p:last-child { margin: 6px 0 0; color: var(--ink-2); font-size: 12px; }
	.prepare-groups { min-width: 210px; border: 1px solid var(--rule); border-radius: 7px; margin: 0; padding: 10px; }
	.prepare-groups legend { color: var(--ink-3); font-size: 10px; font-weight: 600; }
	.prepare-groups label { display: flex; align-items: center; gap: 6px; margin-top: 5px; }
	.prepare-groups input { width: auto; }
	.prepare-groups small { color: var(--ink-3); text-transform: capitalize; }
	.prepare-groups p:last-child { font-size: 9px; }
	.empty { border: 1px dashed var(--rule); border-radius: 10px; padding: 54px 28px; text-align: center; }
	.empty h2 { margin: 0; font: 500 28px Fraunces, Georgia, serif; }
	.empty > p:last-of-type { max-width: 590px; margin: 12px auto 20px; color: var(--ink-2); font-size: 14px; line-height: 1.6; }
	.error { border: 1px solid #e2b9ae; border-radius: 7px; background: #f8e9e5; color: #873f30; margin-bottom: 18px; padding: 10px 12px; font-size: 13px; }
	.confirm-backdrop { position: fixed; z-index: 50; inset: 0; display: grid; place-items: center; background: rgb(18 23 21 / .48); padding: 18px; }
	.confirm-dialog { width: min(100%, 470px); border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); box-shadow: 0 20px 60px rgb(0 0 0 / .18); padding: 22px; }
	.confirm-dialog h2 { margin: 0; font: 500 25px Fraunces, Georgia, serif; }
	.confirm-dialog > p:not(.eyebrow) { color: var(--ink-2); font-size: 13px; line-height: 1.5; }
	.confirm-dialog > div { display: flex; justify-content: end; gap: 8px; margin-top: 18px; }
	@media (max-width: 980px) { .status-board { grid-template-columns: repeat(4, 1fr); } .path-health { grid-template-columns: 1fr; } }
	@media (max-width: 840px) { .workspace { grid-template-columns: 1fr; } .path-list { position: static; } .path-list ol { grid-template-columns: repeat(2, 1fr); } .path-summary { grid-template-columns: repeat(2, 1fr); } }
	@media (max-width: 640px) { .unit-page { padding: 28px 16px 60px; } .unit-head, .head-actions, .inspector-head, .section-head, .prepare { align-items: stretch; flex-direction: column; } .history-panel .section-head > p { text-align: left; } .path-list ol, .two, .dependency-grid { grid-template-columns: 1fr; } .status-board { grid-template-columns: repeat(2, 1fr); } .inspector { padding: 18px; } }
</style>
