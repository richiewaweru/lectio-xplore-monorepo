<script lang="ts">
	import { onMount } from 'svelte';
	import { getLessonActual, getMarksSummary, saveLessonActual, saveMarks } from '$lib/api/units';
	import type { LessonActual, LessonActualStatus, LessonPace, MarksSummary, PathLesson, UnitGroups, UnitPath } from '$lib/types/units';

	let { unitId, path, lessons, groups }: { unitId: string; path: UnitPath; lessons: PathLesson[]; groups: UnitGroups | null } = $props();
	let lessonId = $state('');
	let groupId = $state<string>('');
	let actual = $state<LessonActual | null>(null);
	let marks = $state<MarksSummary | null>(null);
	let status = $state<LessonActualStatus>('partial');
	let pace = $state<LessonPace>('not_recorded');
	let established = $state('');
	let unresolved = $state('');
	let anchor = $state('');
	let note = $state('');
	let counts = $state<Record<string, number>>({});
	let busy = $state<'load' | 'actual' | 'marks' | null>(null);
	let error = $state<string | null>(null);

	const lesson = $derived(lessons.find((item) => item.id === lessonId) ?? null);

	function lines(value: string): string[] {
		return value.split('\n').map((item) => item.trim()).filter(Boolean);
	}

	function fillActual(value: LessonActual | null): void {
		actual = value;
		status = value?.status ?? 'partial';
		pace = value?.pace ?? 'not_recorded';
		established = value?.established_concepts.join('\n') ?? lesson?.must_establish.join('\n') ?? '';
		unresolved = value?.unresolved_misconceptions.join('\n') ?? '';
		anchor = value?.anchor_used ?? '';
		note = value?.teacher_note ?? '';
	}

	function fillMarks(value: MarksSummary | null): void {
		marks = value;
		counts = Object.fromEntries(
			(value?.items ?? []).flatMap((item) => item.option_counts.map((option) => [`${item.item_id}:${option.option_id}`, option.count]))
		);
	}

	async function load(): Promise<void> {
		if (!lesson) return;
		busy = 'load'; error = null; marks = null;
		try {
			const loadedActual = await getLessonActual(unitId, lesson.id);
			fillActual(loadedActual);
			if (lesson.pack_id) fillMarks(await getMarksSummary(unitId, lesson.id, groupId || null));
			else fillMarks(null);
		} catch (err) { error = err instanceof Error ? err.message : 'Could not load lesson results.'; }
		finally { busy = null; }
	}

	async function saveActual(event: SubmitEvent): Promise<void> {
		event.preventDefault(); if (!lesson) return;
		busy = 'actual'; error = null;
		try {
			fillActual(await saveLessonActual(unitId, path, lesson, {
				actual_revision: actual?.revision ?? 0, status, pace,
				established_concepts: status === 'not_taught' ? [] : lines(established),
				unresolved_misconceptions: lines(unresolved),
				anchor_used: anchor.trim() || null, teacher_note: note.trim() || null
			}));
		} catch (err) { error = err instanceof Error ? err.message : 'Could not save the lesson actual.'; }
		finally { busy = null; }
	}

	async function saveAggregateMarks(): Promise<void> {
		if (!lesson || !marks) return;
		busy = 'marks'; error = null;
		try {
			fillMarks(await saveMarks(unitId, path, lesson, {
				marks_revision: marks.revision, group_id: groupId || null,
				items: marks.items.map((item) => ({
					item_id: item.item_id,
					option_counts: Object.fromEntries(item.option_counts.map((option) => [option.option_id, Math.max(0, Number(counts[`${item.item_id}:${option.option_id}`] ?? 0))]))
				}))
			}));
		} catch (err) { error = err instanceof Error ? err.message : 'Could not save aggregate marks.'; }
		finally { busy = null; }
	}

	onMount(() => {
		lessonId = lessons[0]?.id ?? '';
		void load();
	});
</script>

<section class="results" aria-labelledby="results-title">
	<div class="results-head"><div><p class="eyebrow">Actuals and aggregate marks</p><h2 id="results-title">Record what happened</h2><p>Use class-level counts only. Xplore does not create learner accounts or individual diagnoses.</p></div></div>
	<div class="selectors">
		<label><span>Lesson</span><select bind:value={lessonId} onchange={() => void load()}>{#each lessons as item}<option value={item.id}>{item.title}</option>{/each}</select></label>
		<label><span>Group</span><select bind:value={groupId} onchange={() => void load()}><option value="">Whole class</option>{#each groups?.groups ?? [] as group}<option value={group.id}>{group.label}</option>{/each}</select></label>
	</div>
	{#if error}<p class="results-error" role="alert">{error}</p>{/if}
	{#if busy === 'load'}<p role="status">Loading results…</p>{/if}
	{#if lesson}
		<div class="results-grid">
			<form class="actual-card" onsubmit={saveActual}>
				<div><p class="eyebrow">Lesson actual</p><h3>{lesson.title}</h3>{#if actual}<span>Revision {actual.revision} · audited</span>{/if}</div>
				<div class="two"><label><span>Outcome</span><select bind:value={status}><option value="established">Established</option><option value="partial">Partial</option><option value="recovery_needed">Recovery needed</option><option value="not_taught">Not taught</option></select></label><label><span>Pace</span><select bind:value={pace}><option value="not_recorded">Not recorded</option><option value="faster">Faster</option><option value="as_planned">As planned</option><option value="slower">Slower</option></select></label></div>
				{#if status !== 'not_taught'}<label><span>Capabilities established <small>one per line</small></span><textarea bind:value={established}></textarea></label>{/if}
				<label><span>Unresolved misconceptions <small>one ID or note per line</small></span><textarea bind:value={unresolved}></textarea></label>
				<label><span>Anchor used</span><input bind:value={anchor} /></label>
				<label><span>Teacher note</span><textarea bind:value={note}></textarea></label>
				<button class="primary" type="submit" disabled={busy !== null}>{busy === 'actual' ? 'Saving…' : actual ? 'Save new revision' : 'Record actual'}</button>
			</form>
			<section class="marks-card">
				<div><p class="eyebrow">Shared checks</p><h3>Aggregate option counts</h3>{#if marks?.revision}<span>Revision {marks.revision}</span>{/if}</div>
				{#if !lesson.pack_id}<p>Prepare this lesson before entering marks against its pack-owned shared items.</p>
				{:else if marks}
					{#if marks.items.length}{#each marks.items as item}<article><strong>{item.stem}</strong><div class="options">{#each item.option_counts as option}<label><span>{option.option_id}. {option.text}{#if option.misconception_id}<small>tagged: {option.misconception_id}</small>{/if}</span><input aria-label={`${item.stem} ${option.option_id} count`} type="number" min="0" value={counts[`${item.item_id}:${option.option_id}`] ?? 0} oninput={(event) => (counts[`${item.item_id}:${option.option_id}`] = Number(event.currentTarget.value))} /></label>{/each}</div><small>{item.total_count} responses in saved revision</small></article>{/each}<button class="primary" type="button" disabled={busy !== null} onclick={saveAggregateMarks}>{busy === 'marks' ? 'Saving…' : 'Save marks'}</button>{:else}<p>No current shared items are available for this lesson.</p>{/if}
					<div class="advisory"><strong>Advisory summary</strong><p>{marks.advisory_note}</p>{#if marks.misconceptions.length}<ul>{#each marks.misconceptions as item}<li><strong>{item.count}</strong> responses → consistent with {item.label}</li>{/each}</ul>{:else}<p>No tagged misconception count has been recorded.</p>{/if}{#if marks.unclaimed_distractor_count}<p>{marks.unclaimed_distractor_count} distractor responses have no misconception tag and remain unclaimed.</p>{/if}</div>
				{/if}
			</section>
		</div>
	{/if}
</section>

<style>
	.results { max-width: 1180px; margin: 0 auto; }.results-head h2 { margin: 0; font: 500 24px Fraunces, Georgia, serif; }.results-head p:last-child { color: var(--ink-2); font-size: 12px; }.eyebrow { margin: 0 0 5px; color: var(--ink-3); font: 500 9px 'IBM Plex Mono', monospace; letter-spacing: .1em; text-transform: uppercase; }
	.selectors, .two { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }.selectors { margin: 16px 0; }.results-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }.actual-card, .marks-card { display: grid; align-content: start; gap: 12px; border: 1px solid var(--rule); border-radius: 9px; background: var(--surface); padding: 16px; }.actual-card > div:first-child, .marks-card > div:first-child { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }.actual-card h3, .marks-card h3 { margin: 0; }.actual-card span, .marks-card span { color: var(--ink-3); font-size: 9px; }
	label { display: grid; gap: 5px; color: var(--ink-2); font-size: 11px; font-weight: 600; } label small { color: var(--ink-3); font-weight: 400; } input, textarea, select { box-sizing: border-box; width: 100%; border: 1px solid var(--rule); border-radius: 6px; background: var(--paper); color: var(--ink); padding: 8px; } textarea { min-height: 68px; resize: vertical; }.primary { justify-self: start; border: 1px solid var(--accent); border-radius: 7px; background: var(--accent); color: white; padding: 8px 11px; font-weight: 600; }.primary:disabled { opacity: .5; }
	.marks-card article { border-top: 1px solid var(--rule); padding-top: 12px; }.options { display: grid; gap: 6px; margin: 9px 0; }.options label { grid-template-columns: 1fr 82px; align-items: center; }.options label > span { display: grid; gap: 2px; color: var(--ink-2); font-size: 11px; }.advisory { border-radius: 7px; background: var(--accent-soft); padding: 12px; }.advisory p, .advisory li { color: var(--ink-2); font-size: 11px; line-height: 1.45; }.advisory ul { margin: 8px 0; padding-left: 18px; }.results-error { color: #873f30; font-size: 12px; }
	@media (max-width: 760px) { .results-grid, .selectors, .two { grid-template-columns: 1fr; } }
</style>
