<script lang="ts">
	import { saveUnitGroups } from '$lib/api/units';
	import type { UnitGroup, UnitGroupProfile, UnitGroups } from '$lib/types/units';

	let {
		unitId,
		groups,
		onsaved
	}: {
		unitId: string;
		groups: UnitGroups;
		onsaved: (groups: UnitGroups) => void;
	} = $props();

	type DraftGroup = Omit<UnitGroup, 'id' | 'position' | 'revision'> & { id?: string };

	const declared: Record<UnitGroupProfile, { support_level: 'high' | 'medium' | 'low'; declared_toggles: string[] }> = {
		support: { support_level: 'high', declared_toggles: ['support.high.extra_modelling', 'support.high.drop_independent', 'support.high.extra_contrast'] },
		core: { support_level: 'medium', declared_toggles: [] },
		extension: { support_level: 'low', declared_toggles: ['support.low.add_transfer', 'support.low.drop_orient'] }
	};

	// svelte-ignore state_referenced_locally -- editable draft intentionally snapshots loaded data
	let draft = $state<DraftGroup[]>(groups.groups.map(toDraft));
	let busy = $state(false);
	let error = $state<string | null>(null);

	function toDraft(group: UnitGroup): DraftGroup {
		return {
			id: group.id,
			label: group.label,
			profile: group.profile,
			description: group.description,
			toggle_profile: { ...group.toggle_profile, declared_toggles: [...group.toggle_profile.declared_toggles] },
			voice: { ...group.voice }
		};
	}

	function addGroup(): void {
		const used = new Set(draft.map((group) => group.profile));
		const profile = (['core', 'support', 'extension'] as UnitGroupProfile[]).find((candidate) => !used.has(candidate));
		if (!profile) return;
		const defaults = {
			support: { label: 'Support', description: 'More modelling, guidance, and accessible language.', register_name: 'simple' as const, tone: 'encouraging' as const },
			core: { label: 'Core', description: 'The main class route with balanced language and pacing.', register_name: 'balanced' as const, tone: 'neutral' as const },
			extension: { label: 'Extension', description: 'More independent transfer and application.', register_name: 'formal' as const, tone: 'direct' as const }
		}[profile];
		draft.push({
			label: defaults.label,
			description: defaults.description,
			profile,
			toggle_profile: declared[profile],
			voice: { register_name: defaults.register_name, tone: defaults.tone, notation: null }
		});
	}

	function removeGroup(index: number): void {
		draft.splice(index, 1);
	}

	async function save(): Promise<void> {
		if (draft.some((group) => group.label.trim().length === 0 || group.description.trim().length < 3)) {
			error = 'Every group needs a label and a description.';
			return;
		}
		busy = true; error = null;
		try {
			const saved = await saveUnitGroups(unitId, groups, draft.map((group) => ({
				id: group.id,
				label: group.label.trim(),
				profile: group.profile,
				description: group.description.trim(),
				voice: group.voice
			})));
			draft = saved.groups.map(toDraft);
			onsaved(saved);
		} catch (err) { error = err instanceof Error ? err.message : 'Could not save unit groups.'; }
		finally { busy = false; }
	}
</script>

<section class="panel" aria-labelledby="groups-title">
	<div class="panel-head"><div><p class="eyebrow">Unit groups</p><h2 id="groups-title">Groups</h2><p>Groups change how the lesson is supported and spoken, never the concept, objective, or shared diagnostic questions.</p></div><button class="secondary" type="button" disabled={draft.length >= 3 || busy} onclick={addGroup}>Add group</button></div>
	{#if error}<p class="error" role="alert">{error}</p>{/if}
	{#if draft.length}
		<div class="groups">
			{#each draft as group, index (group.id ?? `${group.profile}-${index}`)}
				<article>
					<div class="group-head"><strong>Booklet {index + 1}</strong><button class="text-button" type="button" onclick={() => removeGroup(index)}>Remove</button></div>
					<div class="two">
						<label><span>Group label</span><input bind:value={group.label} maxlength="80" required /></label>
						<label><span>Structural profile</span><select bind:value={group.profile} disabled={Boolean(group.id)} onchange={() => { group.toggle_profile = declared[group.profile]; }}><option value="support">Support</option><option value="core">Core</option><option value="extension">Extension</option></select></label>
					</div>
					<label><span>Who is this group?</span><textarea bind:value={group.description} minlength="3" maxlength="500" required></textarea></label>
					<div class="two">
						<label><span>Language register</span><select bind:value={group.voice.register_name}><option value="simple">Simple</option><option value="balanced">Balanced</option><option value="formal">Formal</option></select></label>
						<label><span>Tone</span><select bind:value={group.voice.tone}><option value="encouraging">Encouraging</option><option value="neutral">Neutral</option><option value="direct">Direct</option></select></label>
					</div>
					<label><span>Notation override <small>optional</small></span><input bind:value={group.voice.notation} maxlength="120" placeholder="e.g. use ×, not *" /></label>
					<div class="toggles"><span>Everyone</span>{#if declared[group.profile].declared_toggles.length}<ul>{#each declared[group.profile].declared_toggles as toggle}<li>{toggle}</li>{/each}</ul>{:else}<p>Same structure for everyone — no extra adjustments.</p>{/if}</div>
				</article>
			{/each}
		</div>
	{:else}<div class="empty"><h3>No groups yet — describe your class and I'll set them up.</h3><p>Until then, the lesson uses one shared structure for the whole class.</p></div>{/if}
	<div class="actions"><p>{draft.length} of 3 groups · one shared diagnostic item set</p><button class="primary" type="button" disabled={busy} onclick={save}>{busy ? 'Saving…' : 'Save groups'}</button></div>
</section>

<style>
	.panel { max-width: 1180px; margin: 0 auto; border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); padding: 22px; }
	.panel-head, .group-head, .actions { display: flex; align-items: start; justify-content: space-between; gap: 18px; }
	.eyebrow { margin: 0 0 6px; color: var(--ink-3); font: 500 10px 'IBM Plex Mono', monospace; letter-spacing: .1em; text-transform: uppercase; }
	h2 { margin: 0; font: 500 28px Fraunces, Georgia, serif; }
	.panel-head p:last-child { max-width: 700px; color: var(--ink-2); font-size: 13px; line-height: 1.5; }
	.groups { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; border-top: 1px solid var(--rule); margin-top: 18px; padding-top: 18px; }
	.groups article { display: grid; gap: 12px; border: 1px solid var(--rule); border-radius: 8px; background: var(--paper); padding: 15px; }
	.group-head strong { font-size: 13px; }
	.two { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
	label { display: grid; gap: 5px; color: var(--ink-2); font-size: 11px; font-weight: 600; }
	label small { color: var(--ink-3); font-weight: 400; }
	input, textarea, select { box-sizing: border-box; width: 100%; border: 1px solid var(--rule); border-radius: 6px; background: var(--surface); padding: 8px 9px; font: inherit; }
	textarea { min-height: 74px; resize: vertical; }
	.toggles { border-radius: 7px; background: var(--surface); padding: 10px; }
	.toggles > span { color: var(--accent); font: 600 10px 'IBM Plex Mono', monospace; text-transform: uppercase; }
	.toggles ul { margin: 8px 0 0; padding-left: 17px; }
	.toggles li, .toggles p { color: var(--ink-3); font-size: 9px; overflow-wrap: anywhere; }
	.actions { align-items: center; border-top: 1px solid var(--rule); margin-top: 18px; padding-top: 16px; }
	.actions p { color: var(--ink-3); font-size: 11px; }
	.primary, .secondary { border-radius: 7px; padding: 9px 13px; font: 600 13px inherit; }
	.primary { border: 1px solid var(--accent); background: var(--accent); color: white; }
	.secondary { border: 1px solid var(--rule); background: var(--surface); color: var(--ink); }
	.text-button { border: 0; background: transparent; color: var(--ink-3); font-size: 11px; }
	button { cursor: pointer; }
	button:disabled { cursor: not-allowed; opacity: .45; }
	.error { border: 1px solid #e2b9ae; border-radius: 7px; background: #f8e9e5; color: #873f30; padding: 10px 12px; font-size: 13px; }
	.empty { border: 1px dashed var(--rule); border-radius: 8px; margin-top: 18px; padding: 30px; text-align: center; }
	.empty p { color: var(--ink-2); font-size: 13px; }
	@media (max-width: 900px) { .groups { grid-template-columns: 1fr; } }
	@media (max-width: 600px) { .panel-head { align-items: stretch; flex-direction: column; } .two { grid-template-columns: 1fr; } }
</style>
