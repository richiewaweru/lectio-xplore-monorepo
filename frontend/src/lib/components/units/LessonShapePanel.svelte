<script lang="ts">
	import { decideShapeDeviation, getLessonShape, requestShapeDeviation } from '$lib/api/units';
	import type { LessonMode, LessonShapePreview, PathLesson, SkeletonVariantShape, UnitPath } from '$lib/types/units';

	let { unitId, path, lesson, shape, lessonMode, misconceptionCount, onsettings, onshape, onrevision }: {
		unitId: string; path: UnitPath; lesson: PathLesson; shape: LessonShapePreview;
		lessonMode: LessonMode; misconceptionCount: number;
		onsettings: (mode: LessonMode, count: number) => Promise<void>;
		onshape: (value: LessonShapePreview) => void;
		onrevision: (revision: number) => Promise<void>;
	} = $props();

	let operation = $state<'insert' | 'remove' | 'replace' | 'reorder'>('replace');
	let targetSlot = $state('');
	let replacementSlot = $state('');
	let reason = $state('');
	let busy = $state<string | null>(null);
	let localError = $state<string | null>(null);
	const profiles = $derived([{ label: 'Canonical', shape: shape.canonical }, ...shape.variants.map((variant) => ({ label: variant.group_profile[0].toUpperCase() + variant.group_profile.slice(1), shape: variant }))]);
	const targetSlots = $derived([...new Set(shape.canonical.slots.map((slot) => slot.slot_id))]);
	const replacementSlots = $derived(shape.available_slots.filter((slot) => operation === 'reorder' || slot !== 'check'));

	async function refresh(): Promise<void> { onshape(await getLessonShape(unitId, lesson.id, lessonMode, misconceptionCount)); }

	async function requestDeviation(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (!targetSlot || reason.trim().length < 3) return;
		busy = 'request'; localError = null;
		try {
			await requestShapeDeviation(unitId, path, lesson, { lesson_mode: lessonMode, operation, target_slot: targetSlot, replacement_slot: operation === 'remove' ? null : replacementSlot || null, reason: reason.trim() });
			reason = ''; await refresh();
		} catch (error) { localError = error instanceof Error ? error.message : 'Could not request the deviation.'; }
		finally { busy = null; }
	}

	async function decide(deviationId: string, decision: 'approve' | 'reject'): Promise<void> {
		busy = `${decision}-${deviationId}`; localError = null;
		try {
			const result = await decideShapeDeviation(unitId, path, lesson, deviationId, decision);
			if (decision === 'approve') await onrevision(result.lesson_revision);
			await refresh();
		} catch (error) { localError = error instanceof Error ? error.message : `Could not ${decision} the deviation.`; }
		finally { busy = null; }
	}

	function diffLabel(item: SkeletonVariantShape['structural_diff'][number]): string {
		if (item.operation === 'replace') return `${item.slot_id} → ${item.replacement_slot}`;
		if (item.operation === 'reorder') return `move ${item.slot_id} before ${item.replacement_slot}`;
		return `${item.operation} ${item.replacement_slot ?? item.slot_id}`;
	}
</script>

<section class="shape" aria-labelledby="shape-title">
	<div class="section-head">
		<div><p class="eyebrow">Controlled lesson shape</p><h3 id="shape-title">{shape.skeleton_id}</h3><p>Every booklet keeps concept <code>{shape.concept_id}</code>, the exact path objective, scope exclusions, and one shared check.</p></div>
		<div class="shape-settings">
			<label><span>Mode</span><select value={lessonMode} onchange={(event) => void onsettings(event.currentTarget.value as LessonMode, misconceptionCount)}><option value="first_exposure">First exposure</option><option value="consolidation">Consolidation</option><option value="repair">Repair</option><option value="retrieval">Retrieval</option><option value="transfer">Transfer</option></select></label>
			<label><span>Misconception slots</span><select value={misconceptionCount} onchange={(event) => void onsettings(lessonMode, Number(event.currentTarget.value))}><option value="0">0</option><option value="1">1</option><option value="2">2</option><option value="3">3</option></select></label>
		</div>
	</div>
	<p class="preview-note">This count stress-tests the shape before preparation. The approved card count is checked again before variants are created.</p>
	{#if shape.blocking_issues.length}<div class="shape-blocked" role="alert"><strong>Preparation blocked</strong><ul>{#each shape.blocking_issues as issue}<li><code>{issue.code}</code> · {issue.group_profile}: {issue.message}</li>{/each}</ul><p>Request a narrower approved deviation or reduce the misconception load; nothing will be silently dropped.</p></div>{/if}

	<div class="shape-grid">
		{#each profiles as profile}<article><div class="variant-title"><strong>{profile.label}</strong>{#if profile.label === 'Canonical'}<span>base</span>{:else}<span>{profile.shape.support_level} support</span>{/if}</div><ol>{#each profile.shape.slots as slot}<li class:locked={slot.locked}>{slot.role}{#if slot.locked}<small>shared</small>{/if}</li>{/each}</ol>{#if profile.shape.structural_diff.length}<ul class="diffs">{#each profile.shape.structural_diff as item}<li><span>{diffLabel(item)}</span><p>{item.explanation}</p><code>{item.toggle_id}</code></li>{/each}</ul>{:else}<p class="no-diff">No structural changes.</p>{/if}</article>{/each}
	</div>

	<div class="deviations">
		<div><p class="eyebrow">Outside declared toggles</p><h4>Teacher-approved deviations</h4><p>Requests do not affect generation until separately approved. Approval increments the lesson revision and makes any existing preparation stale.</p></div>
		{#if localError}<p class="local-error" role="alert">{localError}</p>{/if}
		{#if shape.deviations.length}<div class="deviation-list">{#each shape.deviations as deviation}<article><div><strong>{deviation.operation} {deviation.target_slot}{deviation.replacement_slot ? ` → ${deviation.replacement_slot}` : ''}</strong><span data-status={deviation.status}>{deviation.status.replace('_', ' ')}</span><p>{deviation.reason}</p></div>{#if deviation.status === 'pending_teacher'}<div><button type="button" class="secondary" disabled={busy !== null} onclick={() => decide(deviation.id, 'reject')}>Reject</button><button type="button" class="primary" disabled={busy !== null} onclick={() => decide(deviation.id, 'approve')}>Approve deviation</button></div>{/if}</article>{/each}</div>{/if}
		<form class="deviation-form" onsubmit={requestDeviation}>
			<label><span>Operation</span><select bind:value={operation}><option value="insert">Insert before</option><option value="remove">Remove</option><option value="replace">Replace</option><option value="reorder">Move before</option></select></label>
			<label><span>Target slot</span><select bind:value={targetSlot} required><option value="">Choose…</option>{#each targetSlots as slot}<option value={slot}>{slot}</option>{/each}</select></label>
			{#if operation !== 'remove'}<label><span>{operation === 'insert' ? 'Slot to insert' : operation === 'replace' ? 'Replacement slot' : 'Move before slot'}</span><select bind:value={replacementSlot} required><option value="">Choose…</option>{#each replacementSlots as slot}<option value={slot}>{slot}</option>{/each}</select></label>{/if}
			<label class="reason"><span>Pedagogical reason</span><textarea bind:value={reason} minlength="3" maxlength="500" required placeholder="Explain why the declared profile is insufficient for this objective."></textarea></label>
			<button class="secondary" type="submit" disabled={busy !== null || !targetSlot || (operation !== 'remove' && !replacementSlot) || reason.trim().length < 3}>{busy === 'request' ? 'Requesting…' : 'Request deviation'}</button>
		</form>
	</div>
</section>

<style>
	.shape { border-top: 1px solid var(--rule); margin-top: 26px; padding-top: 22px; }
	.section-head { display: flex; align-items: end; justify-content: space-between; gap: 18px; }
	.section-head h3, h4 { margin: 0; font: 500 19px Fraunces, Georgia, serif; }
	.section-head p:not(.eyebrow), .deviations > div > p:last-child, .preview-note { color: var(--ink-2); font-size: 11px; line-height: 1.5; }
	.eyebrow { margin: 0 0 5px; color: var(--ink-3); font: 500 9px 'IBM Plex Mono', monospace; letter-spacing: .1em; text-transform: uppercase; }
	code { overflow-wrap: anywhere; font: 500 9px 'IBM Plex Mono', monospace; }
	.shape-settings { display: grid; grid-template-columns: 150px 150px; gap: 8px; }
	label { display: grid; gap: 5px; color: var(--ink-2); font-size: 11px; font-weight: 600; }
	select, textarea { box-sizing: border-box; width: 100%; border: 1px solid var(--rule); border-radius: 6px; background: var(--paper); color: var(--ink); padding: 8px 9px; font: inherit; }
	.shape-blocked { border: 1px solid #dfb294; border-radius: 8px; background: #fff7ed; color: #7b4625; margin-top: 14px; padding: 12px 14px; font-size: 11px; }
	.shape-blocked ul { margin: 8px 0; padding-left: 18px; }
	.shape-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 9px; margin-top: 14px; }
	.shape-grid > article { border: 1px solid var(--rule); border-radius: 8px; background: var(--surface); padding: 11px; }
	.variant-title { display: flex; justify-content: space-between; gap: 6px; }
	.variant-title strong { font-size: 12px; }
	.variant-title span { color: var(--ink-3); font-size: 8px; text-transform: uppercase; }
	.shape-grid ol { display: grid; gap: 4px; margin: 10px 0; padding: 0; list-style: none; }
	.shape-grid ol li { display: flex; justify-content: space-between; border-radius: 5px; background: var(--paper); color: var(--ink-2); padding: 5px 7px; font-size: 9px; }
	.shape-grid ol li.locked { background: var(--accent-soft); color: var(--accent); }
	.shape-grid ol small { font-size: 7px; text-transform: uppercase; }
	.diffs { display: grid; gap: 6px; border-top: 1px solid var(--rule); margin: 10px 0 0; padding: 9px 0 0; list-style: none; }
	.diffs span { color: var(--accent); font-size: 9px; font-weight: 600; }
	.diffs p { margin: 2px 0; color: var(--ink-2); font-size: 8px; line-height: 1.35; }
	.diffs code { color: var(--ink-3); font-size: 7px; }
	.no-diff { border-top: 1px solid var(--rule); margin: 10px 0 0; padding-top: 9px; color: var(--ink-3); font-size: 8px; }
	.deviations { border: 1px solid var(--rule); border-radius: 8px; background: var(--paper); margin-top: 16px; padding: 14px; }
	.deviation-list { display: grid; gap: 7px; margin-top: 12px; }
	.deviation-list article { display: flex; align-items: center; justify-content: space-between; gap: 12px; border: 1px solid var(--rule); border-radius: 7px; background: var(--surface); padding: 10px; }
	.deviation-list strong { font-size: 10px; }
	.deviation-list span { border-radius: 999px; background: var(--paper); margin-left: 7px; padding: 3px 6px; color: var(--ink-3); font-size: 7px; text-transform: uppercase; }
	.deviation-list span[data-status='approved'] { background: var(--accent-soft); color: var(--accent); }
	.deviation-list p { margin: 4px 0 0; color: var(--ink-2); font-size: 9px; }
	.deviation-list article > div:last-child { display: flex; gap: 5px; }
	.deviation-form { display: grid; grid-template-columns: 130px 130px 150px minmax(220px, 1fr) auto; align-items: end; gap: 8px; margin-top: 13px; }
	.reason textarea { min-height: 52px; resize: vertical; }
	.primary, .secondary { border-radius: 6px; padding: 8px 10px; font: 600 11px inherit; }
	.primary { border: 1px solid var(--accent); background: var(--accent); color: white; }
	.secondary { border: 1px solid var(--rule); background: var(--surface); color: var(--ink); }
	button:disabled { cursor: not-allowed; opacity: .45; }
	.local-error { border: 1px solid #e2b9ae; border-radius: 6px; background: #f8e9e5; color: #873f30; padding: 8px; font-size: 10px; }
	@media (max-width: 1050px) { .shape-grid { grid-template-columns: repeat(2, 1fr); } .deviation-form { grid-template-columns: repeat(2, 1fr); } .reason { grid-column: 1 / -1; } }
	@media (max-width: 640px) { .section-head { align-items: stretch; flex-direction: column; } .shape-settings, .shape-grid, .deviation-form { grid-template-columns: 1fr; } .reason { grid-column: auto; } .deviation-list article { align-items: stretch; flex-direction: column; } }
</style>
