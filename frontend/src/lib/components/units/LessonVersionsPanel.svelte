<script lang="ts">
	import UnitGroupsPanel from '$lib/components/units/UnitGroupsPanel.svelte';
	import type { UnitGroups } from '$lib/types/units';

	let {
		unitId,
		groups,
		onsaved,
		onclose
	}: {
		unitId: string;
		groups: UnitGroups;
		onsaved: (groups: UnitGroups) => void;
		onclose: () => void;
	} = $props();

	let editing = $state(false);
</script>

<div class="versions-backdrop" role="presentation">
	<div class="versions-dialog" role="dialog" aria-modal="true" aria-labelledby="versions-title">
		<div class="versions-head">
			<div><p class="eyebrow">Versions</p><h2 id="versions-title">Make versions for my groups</h2></div>
			<button class="text-button" type="button" onclick={onclose}>Close</button>
		</div>
		<p class="quiz-banner">All versions share the same quiz, so you can compare the whole class fairly.</p>
		{#if editing}
			<UnitGroupsPanel
				{unitId}
				{groups}
				onsaved={(saved) => {
					onsaved(saved);
					editing = false;
				}}
			/>
		{:else if groups.groups.length}
			<div class="group-cards">
				{#each groups.groups as group (group.id)}
					<article>
						<h3>{group.label}</h3>
						<p>{group.description}</p>
					</article>
				{/each}
			</div>
			<button class="secondary" type="button" onclick={() => (editing = true)}>Edit groups</button>
		{:else}
			<p class="empty">No groups yet — add one to make a version for a different group of students.</p>
			<button class="primary" type="button" onclick={() => (editing = true)}>Add a group</button>
		{/if}
	</div>
</div>

<style>
	.versions-backdrop { position: fixed; z-index: 50; inset: 0; display: grid; place-items: center; background: rgb(18 23 21 / .48); padding: 18px; }
	.versions-dialog { width: min(100%, 720px); max-height: 85vh; overflow-y: auto; border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); box-shadow: 0 20px 60px rgb(0 0 0 / .18); padding: 24px; }
	.versions-head { display: flex; align-items: start; justify-content: space-between; gap: 18px; margin-bottom: 14px; }
	.eyebrow { margin: 0 0 6px; color: var(--ink-3); font: 500 10px 'IBM Plex Mono', monospace; letter-spacing: .1em; text-transform: uppercase; }
	h2 { margin: 0; font: 500 25px Fraunces, Georgia, serif; }
	.quiz-banner { border-radius: 8px; background: var(--accent-soft); color: var(--accent); margin: 0 0 18px; padding: 11px 13px; font-size: 12px; font-weight: 600; }
	.group-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-bottom: 16px; }
	.group-cards article { border: 1px solid var(--rule); border-radius: 8px; background: var(--paper); padding: 14px; }
	.group-cards h3 { margin: 0 0 6px; font-size: 14px; }
	.group-cards p { margin: 0; color: var(--ink-2); font-size: 12px; line-height: 1.5; }
	.empty { color: var(--ink-2); font-size: 13px; margin: 0 0 14px; }
	.primary, .secondary { border-radius: 7px; cursor: pointer; font: 600 13px inherit; padding: 9px 14px; }
	.primary { border: 1px solid var(--accent); background: var(--accent); color: white; }
	.secondary { border: 1px solid var(--rule); background: var(--surface); color: var(--ink); }
	.text-button { border: 0; background: transparent; color: var(--ink-3); cursor: pointer; font-size: 12px; font-weight: 600; }
</style>
