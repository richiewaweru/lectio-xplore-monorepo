<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { constructorReadback, createUnit, listUnits, planUnitPath } from '$lib/api/units';
	import type { ConstructorReadback, Unit } from '$lib/types/units';

	const GRADE_LEVELS = ['Kindergarten', ...Array.from({ length: 12 }, (_, index) => `Grade ${index + 1}`)];
	const SUBJECTS = [
		'Mathematics', 'English Language Arts', 'Science', 'Biology', 'Chemistry', 'Physics',
		'History', 'Geography', 'Economics', 'Computer Science', 'Art', 'Music', 'Physical Education', 'Other'
	];

	let units = $state<Unit[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	let showCreate = $state(false);
	let step = $state<'ask' | 'clarify' | 'readback'>('ask');
	let subject = $state('');
	let gradeLevel = $state('');
	let rawText = $state('');
	let clarifyingAnswer = $state('');
	let readback = $state<ConstructorReadback | null>(null);
	let correctionOpen = $state(false);
	let correctionText = $state('');
	let thinking = $state(false);
	let lockingIn = $state(false);

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

	function resetCreateFlow(): void {
		step = 'ask';
		subject = '';
		gradeLevel = '';
		rawText = '';
		clarifyingAnswer = '';
		readback = null;
		correctionOpen = false;
		correctionText = '';
	}

	function openCreate(): void {
		resetCreateFlow();
		showCreate = true;
	}

	function closeCreate(): void {
		showCreate = false;
		resetCreateFlow();
	}

	async function planIt(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (!subject || !gradeLevel || rawText.trim().length < 3) return;
		thinking = true;
		error = null;
		try {
			const result = await constructorReadback({
				subject,
				grade_level: gradeLevel,
				raw_text: rawText.trim()
			});
			readback = result;
			step = result.clarifying_question ? 'clarify' : 'readback';
		} catch (err) {
			error = err instanceof Error ? err.message : "Could not read that back — let's try again.";
		} finally {
			thinking = false;
		}
	}

	async function answerClarifyingQuestion(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (clarifyingAnswer.trim().length < 1) return;
		thinking = true;
		error = null;
		try {
			readback = await constructorReadback({
				subject,
				grade_level: gradeLevel,
				raw_text: rawText.trim(),
				clarifying_answer: clarifyingAnswer.trim()
			});
			step = 'readback';
		} catch (err) {
			error = err instanceof Error ? err.message : "Could not read that back — let's try again.";
		} finally {
			thinking = false;
		}
	}

	async function sendCorrection(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (correctionText.trim().length < 1) return;
		thinking = true;
		error = null;
		try {
			readback = await constructorReadback({
				subject,
				grade_level: gradeLevel,
				raw_text: rawText.trim(),
				correction: correctionText.trim()
			});
			correctionText = '';
			correctionOpen = false;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not update that from what you typed.';
		} finally {
			thinking = false;
		}
	}

	async function confirmReadback(): Promise<void> {
		if (!readback) return;
		lockingIn = true;
		error = null;
		try {
			const unit = await createUnit({
				title: readback.title,
				topic: readback.topic,
				subject,
				grade_level: gradeLevel,
				destination_objective: readback.destination_objective,
				starting_knowledge: readback.starting_knowledge,
				curriculum_context: readback.curriculum_context,
				class_notes: readback.class_notes
			});
			try {
				await planUnitPath(unit.id, {
					topic: readback.topic,
					subject,
					grade_level: gradeLevel,
					destination_objective: readback.destination_objective,
					starting_knowledge: readback.starting_knowledge,
					curriculum_context: readback.curriculum_context,
					class_notes: readback.class_notes
				});
			} catch {
				// Unit remains as a recoverable draft; the unit page offers retry.
			}
			await goto(`/units/${encodeURIComponent(unit.id)}`);
		} catch (err) {
			error = err instanceof Error ? err.message : "Could not lock that in — let's try again.";
		} finally {
			lockingIn = false;
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
			<p class="lede">Tell me what you're teaching, and I'll turn it into a numbered list of lessons.</p>
		</div>
		<button class="primary" type="button" onclick={() => (showCreate ? closeCreate() : openCreate())}>
			{showCreate ? 'Close' : '+ New unit'}
		</button>
	</header>

	{#if error}<p class="error" role="alert">{error}</p>{/if}

	{#if showCreate}
		<div class="create-card">
			{#if step === 'ask'}
				<form class="ask-form" onsubmit={planIt}>
					<div class="form-head">
						<div><p class="eyebrow">New unit</p><h2>What are you teaching?</h2></div>
					</div>
					<div class="ask-grid">
						<label>
							<span>Subject</span>
							<select bind:value={subject} required>
								<option value="">Choose…</option>
								{#each SUBJECTS as item}<option value={item}>{item}</option>{/each}
							</select>
						</label>
						<label>
							<span>Grade level</span>
							<select bind:value={gradeLevel} required>
								<option value="">Choose…</option>
								{#each GRADE_LEVELS as item}<option value={item}>{item}</option>{/each}
							</select>
						</label>
					</div>
					<label class="wide">
						<span>What are you teaching? Anything I should know about this class?</span>
						<textarea
							bind:value={rawText}
							required
							minlength="3"
							placeholder="e.g. Photosynthesis for my Grade 8 class — they know plants need light but not the chemistry."
						></textarea>
					</label>
					<div class="form-actions">
						<button class="secondary" type="button" onclick={closeCreate}>Cancel</button>
						<button class="primary" type="submit" disabled={thinking || !subject || !gradeLevel || rawText.trim().length < 3}>
							{thinking ? 'Thinking…' : 'Plan it'}
						</button>
					</div>
				</form>
			{:else if step === 'clarify' && readback?.clarifying_question}
				<form class="ask-form" onsubmit={answerClarifyingQuestion}>
					<div class="form-head">
						<div><p class="eyebrow">One quick question</p><h2>{readback.clarifying_question}</h2></div>
					</div>
					<label class="wide"><span>Your answer</span><input bind:value={clarifyingAnswer} required /></label>
					<div class="form-actions">
						<button class="secondary" type="button" onclick={closeCreate}>Cancel</button>
						<button class="primary" type="submit" disabled={thinking || clarifyingAnswer.trim().length < 1}>
							{thinking ? 'Thinking…' : 'Continue'}
						</button>
					</div>
				</form>
			{:else if step === 'readback' && readback}
				<div class="readback">
					<div class="form-head">
						<div><p class="eyebrow">Readback</p><h2>{readback.title}</h2></div>
					</div>
					<p class="readback-line"><strong>Topic:</strong> {readback.topic}</p>
					<p class="readback-line"><strong>By the end, students can</strong> {readback.destination_objective}</p>
					<p class="readback-line"><strong>I'm assuming they already know</strong> {readback.starting_knowledge.join('; ')}</p>
					{#if readback.curriculum_context}
						<p class="readback-line"><strong>Curriculum note:</strong> {readback.curriculum_context}</p>
					{/if}
					<div class="readback-actions">
						<button class="primary" type="button" disabled={lockingIn} onclick={confirmReadback}>
							{lockingIn ? 'Planning lessons…' : "That's right"}
						</button>
						<button class="text-button" type="button" onclick={() => (correctionOpen = !correctionOpen)}>
							type what's off
						</button>
						<button class="text-button" type="button" onclick={closeCreate}>Cancel</button>
					</div>
					{#if correctionOpen}
						<form class="correction-form" onsubmit={sendCorrection}>
							<input bind:value={correctionText} required placeholder="What should I fix?" />
							<button class="secondary" type="submit" disabled={thinking || correctionText.trim().length < 1}>
								{thinking ? 'Updating…' : 'Update'}
							</button>
						</form>
					{/if}
				</div>
			{/if}
		</div>
	{/if}

	{#if loading}
		<p class="status" role="status">Loading units…</p>
	{:else if units.length === 0 && !showCreate}
		<section class="empty">
			<p class="eyebrow">Get started</p>
			<h2>No units yet</h2>
			<p>Tell me what you're teaching and I'll plan the lessons.</p>
			<button class="primary" type="button" onclick={openCreate}>Get started</button>
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
	.text-button { border: 0; background: transparent; color: var(--ink-3); cursor: pointer; font-size: 13px; font-weight: 600; padding: 9px 4px; }
	button:disabled { cursor: progress; opacity: .6; }
	.create-card { border: 1px solid var(--rule); border-radius: 12px; background: var(--surface); margin-bottom: 34px; padding: 26px; }
	.form-head { display: flex; justify-content: space-between; gap: 24px; margin-bottom: 24px; }
	.form-head h2, .empty h2 { margin: 0; font: 500 25px Fraunces, Georgia, serif; }
	.ask-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 18px; }
	label { display: grid; gap: 7px; color: var(--ink-2); font-size: 12px; font-weight: 600; }
	label.wide { grid-column: 1 / -1; }
	input, textarea, select { box-sizing: border-box; width: 100%; border: 1px solid var(--rule); border-radius: 7px; background: var(--paper); color: var(--ink); font: 400 14px Inter, sans-serif; padding: 10px 11px; }
	textarea { min-height: 110px; resize: vertical; }
	input:focus, textarea:focus, select:focus { border-color: var(--accent); outline: 2px solid color-mix(in srgb, var(--accent) 18%, transparent); }
	.form-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 22px; }
	.readback-line { margin: 0 0 12px; color: var(--ink); font-size: 15px; line-height: 1.6; }
	.readback-line strong { font-weight: 600; }
	.readback-actions { display: flex; align-items: center; gap: 10px; margin-top: 18px; }
	.correction-form { display: flex; gap: 8px; margin-top: 14px; }
	.correction-form input { flex: 1; }
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
	@media (max-width: 640px) { .units-page { padding: 36px 18px 60px; } .page-head, .form-head { align-items: stretch; flex-direction: column; } .ask-grid { grid-template-columns: 1fr; } }
</style>
