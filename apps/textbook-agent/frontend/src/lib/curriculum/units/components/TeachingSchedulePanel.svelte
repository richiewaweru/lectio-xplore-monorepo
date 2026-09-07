<script lang="ts">
	import { saveTeachingSchedule, suggestTeachingSchedule } from '$lib/api/units';
	import type { ScheduleFeasibility, TeachingPeriod, TeachingSchedule, UnitPath } from '$lib/types/units';

	let {
		unitId,
		path,
		schedule,
		onsaved
	}: {
		unitId: string;
		path: UnitPath;
		schedule: TeachingSchedule;
		onsaved: (schedule: TeachingSchedule) => void;
	} = $props();

	// svelte-ignore state_referenced_locally -- editable draft intentionally snapshots loaded data
	let draft = $state<TeachingSchedule>(copySchedule(schedule));
	// svelte-ignore state_referenced_locally -- suggestion default is set when the panel opens
	let periodCount = $state(Math.min(4, Math.max(1, path.lessons.filter((lesson) => !lesson.skipped).length)));
	let minutesPerPeriod = $state(50);
	let busy = $state<string | null>(null);
	let error = $state<string | null>(null);
	let dragged = $state<{ lessonId: string; periodIndex: number } | null>(null);

	function copySchedule(value: TeachingSchedule): TeachingSchedule {
		return {
			...value,
			periods: value.periods.map((period) => ({
				...period,
				lesson_ids: [...period.lesson_ids],
				lessons: period.lessons.map((lesson) => ({ ...lesson })),
				feasibility: { ...period.feasibility }
			})),
			feasibility: { ...value.feasibility }
		};
	}

	function feasibility(estimatedMinutes: number, plannedMinutes: number | null): ScheduleFeasibility {
		if (plannedMinutes === null) {
			return { estimated_minutes: estimatedMinutes, planned_minutes: null, delta_minutes: null, status: 'unplanned' };
		}
		return {
			estimated_minutes: estimatedMinutes,
			planned_minutes: plannedMinutes,
			delta_minutes: plannedMinutes - estimatedMinutes,
			status: plannedMinutes >= estimatedMinutes * 1.15
				? 'comfortable'
				: plannedMinutes >= estimatedMinutes ? 'tight' : 'overloaded'
		};
	}

	function periodFeasibility(period: TeachingPeriod): ScheduleFeasibility {
		return feasibility(
			period.lessons.reduce((total, lesson) => total + lesson.estimated_minutes, 0),
			period.planned_minutes
		);
	}

	function scheduleFeasibility(): ScheduleFeasibility {
		const estimates = draft.periods.map(periodFeasibility);
		const plannedMinutes = estimates.every((value) => value.planned_minutes !== null)
			? estimates.reduce((total, value) => total + (value.planned_minutes ?? 0), 0)
			: null;
		return feasibility(
			estimates.reduce((total, value) => total + value.estimated_minutes, 0),
			plannedMinutes
		);
	}

	async function suggest(): Promise<void> {
		busy = 'suggest'; error = null;
		try { draft = copySchedule(await suggestTeachingSchedule(unitId, path, periodCount, minutesPerPeriod)); }
		catch (err) { error = err instanceof Error ? err.message : 'Could not suggest a schedule.'; }
		finally { busy = null; }
	}

	async function save(): Promise<void> {
		busy = 'save'; error = null;
		try {
			const saved = await saveTeachingSchedule(unitId, path, draft);
			draft = copySchedule(saved);
			onsaved(saved);
		} catch (err) { error = err instanceof Error ? err.message : 'Could not save the schedule.'; }
		finally { busy = null; }
	}

	function moveBoundary(periodIndex: number, lessonIndex: number, direction: -1 | 1): void {
		const source = draft.periods[periodIndex];
		const targetIndex = periodIndex + direction;
		const target = draft.periods[targetIndex];
		if (!source || !target) return;
		if (direction === -1 && lessonIndex !== 0) {
			error = 'Only the first lesson in a period can move to the previous period.';
			return;
		}
		if (direction === 1 && lessonIndex !== source.lessons.length - 1) {
			error = 'Only the last lesson in a period can move to the next period.';
			return;
		}
		const [lesson] = source.lessons.splice(lessonIndex, 1);
		const [lessonId] = source.lesson_ids.splice(lessonIndex, 1);
		if (direction === -1) {
			target.lessons.push(lesson);
			target.lesson_ids.push(lessonId);
		} else {
			target.lessons.unshift(lesson);
			target.lesson_ids.unshift(lessonId);
		}
		error = null;
	}

	function dropInto(targetIndex: number): void {
		if (!dragged || dragged.periodIndex === targetIndex) return;
		const source = draft.periods[dragged.periodIndex];
		const lessonIndex = source.lesson_ids.indexOf(dragged.lessonId);
		const direction = targetIndex > dragged.periodIndex ? 1 : -1;
		if (Math.abs(targetIndex - dragged.periodIndex) !== 1) {
			error = 'Lessons can move only across the adjacent period boundary so path order stays fixed.';
		} else {
			moveBoundary(dragged.periodIndex, lessonIndex, direction);
		}
		dragged = null;
	}

	function addPeriod(): void {
		const source = draft.periods.at(-1);
		if (!source || source.lessons.length < 2) {
			error = 'Suggest a schedule or keep at least two lessons in the final period before splitting it.';
			return;
		}
		const lesson = source.lessons.pop();
		const lessonId = source.lesson_ids.pop();
		if (!lesson || !lessonId) return;
		draft.periods.push({
			id: null,
			title: `Period ${draft.periods.length + 1}`,
			position: draft.periods.length + 1,
			planned_minutes: source.planned_minutes,
			teacher_note: null,
			lesson_ids: [lessonId],
			lessons: [lesson],
			feasibility: { estimated_minutes: lesson.estimated_minutes, planned_minutes: source.planned_minutes, delta_minutes: null, status: 'unplanned' }
		});
		error = null;
	}

	function removePeriod(periodIndex: number): void {
		if (draft.periods.length <= 1) return;
		const removed = draft.periods[periodIndex];
		if (periodIndex === 0) {
			draft.periods[1].lessons.unshift(...removed.lessons);
			draft.periods[1].lesson_ids.unshift(...removed.lesson_ids);
		} else {
			draft.periods[periodIndex - 1].lessons.push(...removed.lessons);
			draft.periods[periodIndex - 1].lesson_ids.push(...removed.lesson_ids);
		}
		draft.periods.splice(periodIndex, 1);
		draft.periods.forEach((period, index) => { period.position = index + 1; });
	}
</script>

<section class="panel" aria-labelledby="schedule-title">
	<div class="panel-head">
		<div><p class="eyebrow">Teaching schedule</p><h2 id="schedule-title">Group the route into periods</h2><p>Time changes these boundaries only. Concept identity, objectives, prerequisites, and path order stay fixed.</p></div>
		<div class="feasibility" data-status={scheduleFeasibility().status}><strong>{scheduleFeasibility().status}</strong><span>{scheduleFeasibility().estimated_minutes} estimated minutes</span></div>
	</div>

	{#if error}<p class="error" role="alert">{error}</p>{/if}

	<form class="suggest" onsubmit={(event) => { event.preventDefault(); void suggest(); }}>
		<label><span>Periods</span><input type="number" min="1" max={path.lessons.length} bind:value={periodCount} /></label>
		<label><span>Minutes per period</span><input type="number" min="10" max="240" bind:value={minutesPerPeriod} /></label>
		<button class="secondary" type="submit" disabled={busy !== null}>{busy === 'suggest' ? 'Suggesting…' : 'Suggest boundaries'}</button>
	</form>

	{#if draft.periods.length}
		<div class="periods">
			{#each draft.periods as period, periodIndex (period.id ?? `new-${periodIndex}`)}
				{@const currentFeasibility = periodFeasibility(period)}
				<article
					ondragover={(event) => event.preventDefault()}
					ondrop={() => dropInto(periodIndex)}
				>
					<div class="period-head">
						<label><span>Period {periodIndex + 1}</span><input aria-label={`Period ${periodIndex + 1} title`} bind:value={period.title} /></label>
						<label><span>Minutes</span><input aria-label={`Period ${periodIndex + 1} minutes`} type="number" min="10" max="240" bind:value={period.planned_minutes} /></label>
						<span class="period-status" data-status={currentFeasibility.status}>{currentFeasibility.estimated_minutes} min · {currentFeasibility.status}</span>
					</div>
					<ol>
						{#each period.lessons as lesson, lessonIndex (lesson.id)}
							<li draggable="true" ondragstart={() => (dragged = { lessonId: lesson.id, periodIndex })}>
								<span><strong>{lesson.title}</strong><small>{lesson.estimated_minutes} estimated minutes</small></span>
								<div>
									<button type="button" aria-label={`Move ${lesson.title} to previous period`} disabled={periodIndex === 0 || lessonIndex !== 0} onclick={() => moveBoundary(periodIndex, lessonIndex, -1)}>←</button>
									<button type="button" aria-label={`Move ${lesson.title} to next period`} disabled={periodIndex === draft.periods.length - 1 || lessonIndex !== period.lessons.length - 1} onclick={() => moveBoundary(periodIndex, lessonIndex, 1)}>→</button>
								</div>
							</li>
						{/each}
					</ol>
					<label><span>Teacher note</span><textarea bind:value={period.teacher_note} placeholder="Optional pacing or resource note"></textarea></label>
					<button class="text-button" type="button" disabled={draft.periods.length <= 1} onclick={() => removePeriod(periodIndex)}>Remove period</button>
				</article>
			{/each}
		</div>
		<div class="actions"><button class="secondary" type="button" onclick={addPeriod}>Add period</button><button class="primary" type="button" disabled={busy !== null || draft.periods.some((period) => period.lessons.length === 0)} onclick={save}>{busy === 'save' ? 'Saving…' : 'Save schedule'}</button></div>
	{:else}
		<div class="empty"><h3>No teaching periods yet</h3><p>Choose a period count and let the deterministic suggestion place boundaries along the path.</p></div>
	{/if}
</section>

<style>
	.panel { max-width: 1180px; margin: 0 auto; border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); padding: 22px; }
	.panel-head { display: flex; justify-content: space-between; gap: 24px; }
	.eyebrow { margin: 0 0 6px; color: var(--ink-3); font: 500 10px 'IBM Plex Mono', monospace; letter-spacing: .1em; text-transform: uppercase; }
	h2 { margin: 0; font: 500 28px Fraunces, Georgia, serif; }
	.panel-head p:last-child, .empty p { max-width: 680px; color: var(--ink-2); font-size: 13px; line-height: 1.5; }
	.feasibility { align-self: start; display: grid; min-width: 180px; border: 1px solid var(--rule); border-radius: 8px; padding: 12px; }
	.feasibility strong { text-transform: capitalize; }
	.feasibility span, .period-status { color: var(--ink-3); font-size: 10px; }
	[data-status='overloaded'] { border-color: #dfb294; background: #fff7ed; color: #8b4c26; }
	.suggest { display: grid; grid-template-columns: 150px 180px auto; align-items: end; gap: 10px; border-top: 1px solid var(--rule); margin-top: 18px; padding-top: 18px; }
	label { display: grid; gap: 5px; color: var(--ink-2); font-size: 11px; font-weight: 600; }
	input, textarea { box-sizing: border-box; width: 100%; border: 1px solid var(--rule); border-radius: 6px; background: var(--paper); padding: 8px 9px; font: inherit; }
	textarea { min-height: 58px; resize: vertical; }
	.periods { display: grid; gap: 12px; margin-top: 20px; }
	.periods article { border: 1px solid var(--rule); border-radius: 8px; background: var(--paper); padding: 16px; }
	.period-head { display: grid; grid-template-columns: minmax(220px, 1fr) 110px auto; align-items: end; gap: 10px; }
	.period-status { border: 1px solid var(--rule); border-radius: 999px; padding: 7px 9px; text-transform: capitalize; }
	ol { display: grid; gap: 5px; margin: 14px 0; padding: 0; list-style: none; }
	li { display: flex; align-items: center; justify-content: space-between; gap: 12px; border: 1px solid var(--rule); border-radius: 7px; background: var(--surface); padding: 9px 10px; }
	li strong, li small { display: block; }
	li strong { font-size: 12px; }
	li small { margin-top: 2px; color: var(--ink-3); font-size: 10px; }
	li div { display: flex; gap: 4px; }
	li button, .text-button { border: 1px solid var(--rule); border-radius: 5px; background: var(--paper); padding: 5px 8px; }
	.actions { display: flex; justify-content: space-between; margin-top: 16px; }
	.primary, .secondary { border-radius: 7px; padding: 9px 13px; font: 600 13px inherit; }
	.primary { border: 1px solid var(--accent); background: var(--accent); color: white; }
	.secondary { border: 1px solid var(--rule); background: var(--surface); color: var(--ink); }
	button { cursor: pointer; }
	button:disabled { cursor: not-allowed; opacity: .45; }
	.error { border: 1px solid #e2b9ae; border-radius: 7px; background: #f8e9e5; color: #873f30; padding: 10px 12px; font-size: 13px; }
	.empty { border: 1px dashed var(--rule); border-radius: 8px; margin-top: 18px; padding: 30px; text-align: center; }
	@media (max-width: 700px) { .panel-head { flex-direction: column; } .suggest, .period-head { grid-template-columns: 1fr; } .feasibility { width: auto; } }
</style>
