<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { createUnit, listUnits } from '$lib/api/units';
	import type { Unit } from '$lib/types/units';

	let units = $state<Unit[]>([]);
	let loading = $state(true);
	let saving = $state(false);
	let error = $state<string | null>(null);
	let showCreate = $state(false);
	let title = $state('');
	let topic = $state('');
	let subject = $state('');
	let gradeLevel = $state('');
	let destinationObjective = $state('');
	let startingKnowledge = $state('');
	let curriculumContext = $state('');

	function lines(value: string): string[] {
		return value.split('\n').map((item) => item.trim()).filter(Boolean);
	}

	async function load(): Promise<void> {
		loading = true;
		error = null;
		try {
			units = await listUnits();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load units.';
		} finally {
			loading = false;
		}
	}

	async function submit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		saving = true;
		error = null;
		try {
			const unit = await createUnit({
				title: title.trim(),
				topic: topic.trim(),
				subject: subject.trim(),
				grade_level: gradeLevel.trim(),
				destination_objective: destinationObjective.trim(),
				starting_knowledge: lines(startingKnowledge),
				curriculum_context: curriculumContext.trim() || null
			});
			await goto(`/units/${encodeURIComponent(unit.id)}`);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not create the unit.';
		} finally {
			saving = false;
		}
	}

	onMount(() => void load());
</script>

<svelte:head><title>Units · Lectio</title></svelte:head>

<div class="units-page">
	<header class="page-head">
		<div>
			<p class="eyebrow">Curriculum workspace</p>
			<h1>Units</h1>
			<p class="lede">Plan the concept route first, then prepare each lesson from its approved objective.</p>
		</div>
		<button class="primary" type="button" onclick={() => (showCreate = !showCreate)}>
			{showCreate ? 'Close' : '+ New unit'}
		</button>
	</header>

	{#if error}<p class="error" role="alert">{error}</p>{/if}

	{#if showCreate}
		<form class="create-card" onsubmit={submit}>
			<div class="form-head">
				<div><p class="eyebrow">New unit</p><h2>Define the destination</h2></div>
				<p>No lesson count or duration is sent to path planning.</p>
			</div>
			<div class="form-grid">
				<label><span>Unit title</span><input required bind:value={title} placeholder="Photosynthesis" /></label>
				<label><span>Topic</span><input required bind:value={topic} placeholder="How plants make food" /></label>
				<label><span>Subject</span><input required bind:value={subject} placeholder="Biology" /></label>
				<label><span>Grade level</span><input required bind:value={gradeLevel} placeholder="Grade 8" /></label>
				<label class="wide"><span>Destination objective</span><textarea required bind:value={destinationObjective} placeholder="Explain how light energy is converted into stored chemical energy."></textarea></label>
				<label class="wide"><span>Starting knowledge <small>one capability per line</small></span><textarea bind:value={startingKnowledge} placeholder="Plants are living things.&#10;Leaves receive light."></textarea></label>
				<label class="wide"><span>Curriculum context <small>optional</small></span><textarea bind:value={curriculumContext} placeholder="Curriculum boundaries, terminology, or assessment context."></textarea></label>
			</div>
			<div class="form-actions">
				<button class="secondary" type="button" onclick={() => (showCreate = false)}>Cancel</button>
				<button class="primary" type="submit" disabled={saving}>{saving ? 'Creating…' : 'Create unit'}</button>
			</div>
		</form>
	{/if}

	{#if loading}
		<p class="status" role="status">Loading units…</p>
	{:else if units.length === 0 && !showCreate}
		<section class="empty">
			<p class="eyebrow">Start with the route</p>
			<h2>No units yet</h2>
			<p>Create a destination-led concept path, approve it, and prepare lessons one at a time.</p>
			<button class="primary" type="button" onclick={() => (showCreate = true)}>Create your first unit</button>
		</section>
	{:else if units.length > 0}
		<section class="unit-list" aria-label="Your units">
			{#each units as unit (unit.id)}
				<a class="unit-row" href={`/units/${encodeURIComponent(unit.id)}`}>
					<div>
						<div class="row-title"><h2>{unit.title}</h2><span class:approved={unit.status === 'approved'}>{unit.status}</span></div>
						<p>{unit.subject} · {unit.grade_level}</p>
						<p class="objective">{unit.destination_objective}</p>
					</div>
					<span class="open">Open →</span>
				</a>
			{/each}
		</section>
	{/if}
</div>

<style>
	.units-page { min-height: calc(100vh - 58px); padding: 54px 28px 80px; }
	.page-head, .create-card, .unit-list, .empty, .status, .error { max-width: 960px; margin-inline: auto; }
	.page-head { display: flex; align-items: end; justify-content: space-between; gap: 24px; margin-bottom: 34px; }
	.eyebrow { margin: 0 0 7px; color: var(--ink-3); font: 500 11px 'IBM Plex Mono', monospace; letter-spacing: .1em; text-transform: uppercase; }
	h1 { margin: 0; font: 500 38px/1.1 Fraunces, Georgia, serif; letter-spacing: -.03em; }
	.lede, .form-head p, .empty > p, .status { color: var(--ink-2); font-size: 14px; line-height: 1.6; }
	.lede { margin: 10px 0 0; }
	button { font: inherit; }
	.primary, .secondary { border-radius: 7px; cursor: pointer; font-size: 13px; font-weight: 600; padding: 9px 15px; }
	.primary { border: 1px solid var(--accent); background: var(--accent); color: white; }
	.secondary { border: 1px solid var(--rule); background: var(--surface); color: var(--ink); }
	button:disabled { cursor: progress; opacity: .6; }
	.create-card { border: 1px solid var(--rule); border-radius: 12px; background: var(--surface); margin-bottom: 34px; padding: 26px; }
	.form-head { display: flex; justify-content: space-between; gap: 24px; margin-bottom: 24px; }
	.form-head h2, .empty h2 { margin: 0; font: 500 25px Fraunces, Georgia, serif; }
	.form-head p { max-width: 280px; margin: 0; text-align: right; }
	.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
	label { display: grid; gap: 7px; color: var(--ink-2); font-size: 12px; font-weight: 600; }
	label small { color: var(--ink-3); font-weight: 400; }
	label.wide { grid-column: 1 / -1; }
	input, textarea { box-sizing: border-box; width: 100%; border: 1px solid var(--rule); border-radius: 7px; background: var(--paper); color: var(--ink); font: 400 14px Inter, sans-serif; padding: 10px 11px; }
	textarea { min-height: 82px; resize: vertical; }
	input:focus, textarea:focus { border-color: var(--accent); outline: 2px solid color-mix(in srgb, var(--accent) 18%, transparent); }
	.form-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 22px; }
	.unit-list { display: grid; border-top: 1px solid var(--rule); }
	.unit-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 20px; border-bottom: 1px solid var(--rule); color: inherit; padding: 22px 16px; text-decoration: none; }
	.unit-row:hover, .unit-row:focus-visible { border-radius: 8px; background: var(--surface); outline: none; }
	.row-title { display: flex; align-items: center; gap: 10px; }
	.row-title h2 { margin: 0; font-size: 17px; font-weight: 600; }
	.row-title span { border-radius: 999px; background: var(--amber-soft); color: var(--amber); font: 500 10px 'IBM Plex Mono', monospace; padding: 3px 7px; text-transform: uppercase; }
	.row-title span.approved { background: var(--accent-soft); color: var(--accent); }
	.unit-row p { margin: 5px 0 0; color: var(--ink-3); font-size: 12px; }
	.unit-row p.objective { color: var(--ink-2); font-size: 13px; }
	.open { color: var(--accent); font-size: 13px; font-weight: 600; }
	.empty { border: 1px dashed var(--rule); border-radius: 10px; padding: 52px 28px; text-align: center; }
	.empty > p { max-width: 520px; margin: 10px auto 20px; }
	.error { border: 1px solid #e2b9ae; border-radius: 7px; background: #f8e9e5; color: #873f30; margin-bottom: 20px; padding: 10px 12px; font-size: 13px; }
	@media (max-width: 640px) { .units-page { padding: 36px 18px 60px; } .page-head, .form-head { align-items: stretch; flex-direction: column; } .form-head p { text-align: left; } .form-grid { grid-template-columns: 1fr; } label.wide { grid-column: auto; } }
</style>
