<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import {
		approveUnitPath,
		getPreparedLessonStatus,
		getUnit,
		getUnitPath,
		mergePathLessons,
		patchPathLesson,
		planUnitPath,
		preparePathLesson,
		previewSkeleton,
		regeneratePathLesson,
		reorderPathLessons,
		skipPathLesson,
		splitPathLesson
	} from '$lib/api/units';
	import type {
		KnowledgeType,
		LessonMode,
		PathLesson,
		PreparedLessonStatus,
		SkeletonPreview,
		Unit,
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
	let shape = $state<SkeletonPreview | null>(null);
	let preparation = $state<PreparedLessonStatus | null>(null);
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
				previewSkeleton(lesson.objective, lessonMode),
				getPreparedLessonStatus(unitId, lesson.id)
			]);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load lesson details.';
		}
	}

	async function load(options: { preserveSelection?: boolean } = {}): Promise<void> {
		loading = true;
		error = null;
		try {
			unit = await getUnit(unitId);
			path = unit.active_path_version_id ? await getUnitPath(unitId) : null;
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
			path = await planUnitPath(unitId, plannerInput(unit as Unit), replan);
			unit = await getUnit(unitId);
			if (path.lessons.length) await selectLesson(path.lessons[0]);
		}, false);
	}

	async function saveLesson(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (!selected) return;
		await act('save', () => patchPathLesson(unitId, selected.id, {
			title: editTitle.trim(), objective: editObjective.trim(),
			must_establish: lines(editMustEstablish), exclusions: lines(editExclusions),
			primary_knowledge_type: editType
		}));
	}

	async function move(offset: number): Promise<void> {
		if (!path || selectedIndex < 0) return;
		const target = selectedIndex + offset;
		if (target < 0 || target >= path.lessons.length) return;
		const ids = path.lessons.map((lesson) => lesson.id);
		[ids[selectedIndex], ids[target]] = [ids[target], ids[selectedIndex]];
		await act('reorder', () => reorderPathLessons(unitId, ids));
	}

	async function splitSelected(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (!selected) return;
		await act('split', () => splitPathLesson(unitId, selected.id, [
			{ concept_candidate: { slug: slug(splitATitle), title: splitATitle.trim() }, objective: splitAObjective.trim(), must_establish: [splitAObjective.trim()], exclusions: selected.exclusions, primary_knowledge_type: selected.primary_knowledge_type, secondary_demand: selected.secondary_demand },
			{ concept_candidate: { slug: slug(splitBTitle), title: splitBTitle.trim() }, objective: splitBObjective.trim(), must_establish: [splitBObjective.trim()], exclusions: selected.exclusions, primary_knowledge_type: selected.primary_knowledge_type, secondary_demand: selected.secondary_demand }
		]));
		showSplit = false;
	}

	async function mergeSelected(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (!selected || !nextLesson) return;
		await act('merge', () => mergePathLessons(unitId, [selected.id, nextLesson.id], {
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
			const prepared = await preparePathLesson(unitId, selected.id, lessonMode);
			window.location.href = `/studio?generation_id=${encodeURIComponent(prepared.generation_id)}`;
		}, false);
	}

	async function regenerate(): Promise<void> {
		if (!selected || regenerationReason.trim().length < 3) return;
		await act('regenerate', async () => {
			const prepared = await regeneratePathLesson(
				unitId,
				selected.id,
				lessonMode,
				regenerationReason.trim()
			);
			window.location.href = `/studio?generation_id=${encodeURIComponent(prepared.generation_id)}`;
		}, false);
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
			<section class="path-summary">
				<div><strong>{path.lessons.length}</strong><span>capabilities</span></div><div><strong>{path.forward_verified ? 'Yes' : 'No'}</strong><span>forward verified</span></div><div><strong>{path.reaches_destination ? 'Yes' : 'No'}</strong><span>destination reached</span></div><div><strong>{path.prerequisite_risks.length}</strong><span>prerequisite risks</span></div>
				{#if path.status !== 'approved'}<button class="primary" type="button" disabled={busy !== null || !path.reaches_destination || path.prerequisite_risks.length > 0} onclick={() => act('approve', async () => { path = await approveUnitPath(unitId); unit = await getUnit(unitId); }, false)}>{busy === 'approve' ? 'Approving…' : 'Approve path'}</button>{/if}
			</section>

			<div class="workspace">
				<aside class="path-list" aria-label="Concept path">
					<p class="eyebrow">Concept path</p>
					<ol>{#each path.lessons as lesson, index (lesson.id)}<li class:active={lesson.id === selectedId} class:skipped={lesson.skipped}><button type="button" onclick={() => selectLesson(lesson)}><span>{index + 1}</span><span><strong>{lesson.title}</strong><small>{lesson.primary_knowledge_type}{lesson.pack_id ? ' · prepared' : ''}</small></span></button></li>{/each}</ol>
				</aside>

				{#if selected}
					<main class="inspector">
						<div class="inspector-head"><div><p class="eyebrow">Capability {selected.position + 1}</p><h2>{selected.title}</h2></div><div class="compact-actions"><button type="button" aria-label="Move lesson up" disabled={selectedIndex <= 0 || busy !== null} onclick={() => move(-1)}>↑</button><button type="button" aria-label="Move lesson down" disabled={selectedIndex >= path.lessons.length - 1 || busy !== null} onclick={() => move(1)}>↓</button><button type="button" disabled={selected.skipped || busy !== null} onclick={() => act('skip', () => skipPathLesson(unitId, selected.id))}>Skip</button></div></div>

						<form class="editor" onsubmit={saveLesson}>
							<label><span>Title</span><input bind:value={editTitle} required /></label>
							<label><span>Objective <small>owned by this path lesson</small></span><textarea bind:value={editObjective} required></textarea></label>
							<div class="two"><label><span>Must establish <small>one per line</small></span><textarea bind:value={editMustEstablish} required></textarea></label><label><span>Exclusions <small>one per line</small></span><textarea bind:value={editExclusions}></textarea></label></div>
							<label><span>Knowledge type</span><select bind:value={editType}><option value="factual">Factual</option><option value="conceptual">Conceptual</option><option value="procedural">Procedural</option><option value="evaluative">Evaluative</option></select></label>
							<button class="secondary" type="submit" disabled={busy !== null}>{busy === 'save' ? 'Saving…' : 'Save lesson changes'}</button>
						</form>

						<div class="structure-actions"><button type="button" class="text-button" onclick={() => (showSplit = !showSplit)}>Split lesson</button><button type="button" class="text-button" disabled={!nextLesson} onclick={() => (showMerge = !showMerge)}>Merge with next</button></div>
						{#if showSplit}<form class="operation-form" onsubmit={splitSelected}><h3>Split into two capabilities</h3><label><span>First title</span><input bind:value={splitATitle} required /></label><label><span>First objective</span><textarea bind:value={splitAObjective} required></textarea></label><label><span>Second title</span><input bind:value={splitBTitle} required /></label><label><span>Second objective</span><textarea bind:value={splitBObjective} required></textarea></label><button class="secondary" type="submit" disabled={busy !== null}>{busy === 'split' ? 'Splitting…' : 'Confirm split'}</button></form>{/if}
						{#if showMerge && nextLesson}<form class="operation-form" onsubmit={mergeSelected}><h3>Merge with {nextLesson.title}</h3><label><span>Merged title</span><input bind:value={mergeTitle} required /></label><label><span>Merged objective</span><textarea bind:value={mergeObjective} required></textarea></label><button class="secondary" type="submit" disabled={busy !== null}>{busy === 'merge' ? 'Merging…' : 'Confirm merge'}</button></form>{/if}

						<section class="shape"><div class="section-head"><div><p class="eyebrow">Lesson shape</p><h3>{shape?.skeleton_id ?? 'Loading preview…'}</h3></div><label><span>Mode</span><select bind:value={lessonMode} onchange={() => selectLesson(selected)}><option value="first_exposure">First exposure</option><option value="consolidation">Consolidation</option><option value="repair">Repair</option><option value="retrieval">Retrieval</option><option value="transfer">Transfer</option></select></label></div>{#if shape}<div class="variants">{#each shape.variants as variant}<div><strong>{variant.group_profile}</strong><ol>{#each variant.slots as slot}<li class:locked={slot.locked}>{slot.role}</li>{/each}</ol>{#if variant.warnings.length}<small>{variant.warnings.join(' · ')}</small>{/if}</div>{/each}</div>{/if}</section>

						<section class="prepare">
							<div><p class="eyebrow">Preparation</p><h3>{preparation?.workflow_stage ?? 'Checking status…'}</h3><p>{preparation?.stale ? 'The existing preparation is stale and must be regenerated.' : 'Preparation enters the durable concept-card review before lesson writing.'}</p></div>
							{#if preparation?.stale && preparation.can_regenerate}
								<form class="regenerate" onsubmit={(event) => { event.preventDefault(); void regenerate(); }}>
									<label><span>Regeneration reason</span><input bind:value={regenerationReason} minlength="3" maxlength="500" required /></label>
									<button class="primary" type="submit" disabled={busy !== null || regenerationReason.trim().length < 3}>{busy === 'regenerate' ? 'Regenerating…' : 'Regenerate preparation'}</button>
								</form>
							{:else if preparation?.generation_id}<a class="primary link" href={`/studio?generation_id=${encodeURIComponent(preparation.generation_id)}`}>Open review</a>{:else}<button class="primary" type="button" disabled={path.status !== 'approved' || selected.skipped || busy !== null} onclick={prepare}>{busy === 'prepare' ? 'Preparing…' : 'Prepare lesson'}</button>{/if}
						</section>
					</main>
				{/if}
			</div>
		{/if}
	{/if}
</div>

<style>
	.unit-page { min-height: calc(100vh - 58px); padding: 38px 28px 80px; }
	.unit-head, .path-summary, .workspace, .empty, .error, .loading { max-width: 1180px; margin-inline: auto; }
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
	.path-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)) auto; align-items: center; gap: 16px; border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); margin-bottom: 22px; padding: 16px 18px; }
	.path-summary div { display: grid; gap: 2px; }
	.path-summary strong { font: 500 20px Fraunces, Georgia, serif; }
	.path-summary span { color: var(--ink-3); font-size: 11px; }
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
	.operation-form { border: 1px solid var(--rule); border-radius: 8px; background: var(--paper); padding: 16px; }
	.operation-form > button { justify-self: start; }
	.shape, .prepare { border-top: 1px solid var(--rule); margin-top: 26px; padding-top: 22px; }
	.section-head label { min-width: 170px; }
	.variants { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 15px; }
	.variants > div { border: 1px solid var(--rule); border-radius: 7px; padding: 12px; }
	.variants strong { font-size: 12px; text-transform: capitalize; }
	.variants ol { display: flex; flex-wrap: wrap; gap: 5px; margin: 10px 0 0; padding: 0; list-style: none; }
	.variants li { border-radius: 999px; background: var(--paper); color: var(--ink-2); font-size: 10px; padding: 4px 7px; }
	.variants li.locked { background: var(--accent-soft); color: var(--accent); }
	.variants small { display: block; margin-top: 8px; color: var(--amber); font-size: 10px; }
	.prepare { align-items: center; }
	.regenerate { display: grid; min-width: min(100%, 360px); gap: 8px; }
	.regenerate button { justify-self: end; }
	.prepare p:last-child { margin: 6px 0 0; color: var(--ink-2); font-size: 12px; }
	.empty { border: 1px dashed var(--rule); border-radius: 10px; padding: 54px 28px; text-align: center; }
	.empty h2 { margin: 0; font: 500 28px Fraunces, Georgia, serif; }
	.empty > p:last-of-type { max-width: 590px; margin: 12px auto 20px; color: var(--ink-2); font-size: 14px; line-height: 1.6; }
	.error { border: 1px solid #e2b9ae; border-radius: 7px; background: #f8e9e5; color: #873f30; margin-bottom: 18px; padding: 10px 12px; font-size: 13px; }
	@media (max-width: 840px) { .workspace { grid-template-columns: 1fr; } .path-list { position: static; } .path-list ol { grid-template-columns: repeat(2, 1fr); } .path-summary { grid-template-columns: repeat(2, 1fr); } .variants { grid-template-columns: 1fr; } }
	@media (max-width: 640px) { .unit-page { padding: 28px 16px 60px; } .unit-head, .head-actions, .inspector-head, .section-head, .prepare { align-items: stretch; flex-direction: column; } .path-list ol, .two { grid-template-columns: 1fr; } .inspector { padding: 18px; } }
</style>
