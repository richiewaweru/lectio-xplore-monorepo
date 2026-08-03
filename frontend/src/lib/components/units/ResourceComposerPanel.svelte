<script lang="ts">
	import { createUnitResource, previewUnitResource } from '$lib/api/units';
	import type { PathLesson, ResourceComposeInput, ResourceComposition, ResourceProjectionType, TeachingSchedule, UnitGroups, UnitPath } from '$lib/types/units';

	let { unitId, path, lessons, groups, schedule, compositions, oncreated }: {
		unitId: string; path: UnitPath; lessons: PathLesson[]; groups: UnitGroups | null;
		schedule: TeachingSchedule | null; compositions: ResourceComposition[];
		oncreated: (composition: ResourceComposition) => void;
	} = $props();

	const projectionOptions: Array<{ value: ResourceProjectionType; label: string }> = [
		{ value: 'full_lesson', label: 'Full lesson' }, { value: 'homework', label: 'Homework' },
		{ value: 'revision_sheet', label: 'Revision sheet' }, { value: 'flashcards', label: 'Flashcards' },
		{ value: 'quiz', label: 'Quiz' }, { value: 'answer_key', label: 'Answer key' },
		{ value: 'unit_exam', label: 'Unit exam' }
	];
	let projection = $state<ResourceProjectionType>('revision_sheet');
	let lessonIds = $state<string[]>([]);
	let periodIds = $state<string[]>([]);
	let groupIds = $state<string[]>([]);
	let initialized = $state(false);
	let componentRefs = $state<string[]>([]);
	let itemIds = $state<string[]>([]);
	let includeKeys = $state(false);
	let includeSupportNotes = $state(false);
	let preview = $state<ResourceComposition | null>(null);
	let busy = $state<'preview' | 'create' | null>(null);
	let error = $state<string | null>(null);

	$effect(() => {
		if (initialized) return;
		lessonIds = lessons.filter((lesson) => lesson.pack_id).map((lesson) => lesson.id);
		groupIds = groups?.groups.map((group) => group.id) ?? [];
		initialized = true;
	});

	function input(useSelections = true): ResourceComposeInput {
		return { projection, path_lesson_ids: lessonIds, period_ids: periodIds, group_ids: groupIds,
			component_refs: useSelections ? componentRefs : [], item_ids: useSelections ? itemIds : [],
			include_keys: includeKeys, include_support_notes: includeSupportNotes };
	}

	async function showPreview(useSelections = false): Promise<void> {
		busy = 'preview'; error = null;
		try {
			preview = await previewUnitResource(unitId, path, input(useSelections));
			if (!useSelections) {
				componentRefs = [...preview.selected_component_refs];
				itemIds = [...preview.selected_item_ids];
			}
		} catch (err) { error = err instanceof Error ? err.message : 'Could not preview this resource.'; }
		finally { busy = null; }
	}

	async function createResource(): Promise<void> {
		busy = 'create'; error = null;
		try {
			const created = await createUnitResource(unitId, path, input(true));
			preview = created; oncreated(created);
		} catch (err) { error = err instanceof Error ? err.message : 'Could not create this resource.'; }
		finally { busy = null; }
	}

	function exportResource(composition: ResourceComposition): void {
		const blob = new Blob([JSON.stringify(composition.document, null, 2)], { type: 'application/json' });
		const url = URL.createObjectURL(blob);
		const anchor = document.createElement('a'); anchor.href = url;
		anchor.download = `${composition.projection}-${composition.id ?? 'preview'}.json`; anchor.click();
		URL.revokeObjectURL(url);
	}
</script>

<section class="resources" aria-labelledby="resources-title">
	<div class="resource-head"><div><p class="eyebrow">Deterministic projections</p><h2 id="resources-title">Create classroom resources</h2><p>Compose approved lesson material and shared items without another model call.</p></div><span>{compositions.length} saved</span></div>
	<div class="composer-grid">
		<fieldset><legend>Type</legend>{#each projectionOptions as option}<label><input type="radio" bind:group={projection} value={option.value} onchange={() => (preview = null)} /> {option.label}</label>{/each}</fieldset>
		<fieldset><legend>Concepts</legend>{#each lessons as lesson}<label><input type="checkbox" bind:group={lessonIds} value={lesson.id} disabled={!lesson.pack_id} /> {lesson.title}{#if !lesson.pack_id}<small>not prepared</small>{/if}</label>{/each}</fieldset>
		<fieldset><legend>Periods</legend>{#if schedule?.periods.length}{#each schedule.periods as period}<label><input type="checkbox" bind:group={periodIds} value={period.id} /> {period.title}</label>{/each}{:else}<p>No teaching periods saved.</p>{/if}</fieldset>
		<fieldset><legend>Groups</legend>{#if groups?.groups.length}{#each groups.groups as group}<label><input type="checkbox" bind:group={groupIds} value={group.id} /> {group.label}</label>{/each}{:else}<p>Everyone — one shared lesson for the whole class.</p>{/if}</fieldset>
	</div>
	<div class="projection-options">
		<label><input type="checkbox" bind:checked={includeKeys} /> Include answer key</label>
		{#if projection === 'homework'}<label><input type="checkbox" bind:checked={includeSupportNotes} /> Include support notes</label>{/if}
		<button class="secondary" type="button" disabled={busy !== null || (!lessonIds.length && !periodIds.length)} onclick={() => showPreview(false)}>{busy === 'preview' ? 'Previewing…' : 'Preview'}</button>
	</div>
	{#if error}<p class="resource-error" role="alert">{error}</p>{/if}
	{#if preview}
		<section class:unavailable={!preview.can_create} class="preview" aria-label="Resource preview">
			<div><p class="eyebrow">Preview</p><h3>{projectionOptions.find((option) => option.value === preview?.projection)?.label}</h3><span>{preview.template_version}</span></div>
			{#if preview.unavailable_reasons?.length}<div role="alert"><strong>Projection unavailable</strong><ul>{#each preview.unavailable_reasons as reason}<li>{reason}</li>{/each}</ul></div>{/if}
			{#if preview.available_components?.length}<details open><summary>Approved components · {componentRefs.length} selected</summary><div class="choices">{#each preview.available_components as component}<label><input type="checkbox" bind:group={componentRefs} value={component.ref} /><span><strong>{component.title}</strong><small>{component.lesson_title} · {component.group_label} · {component.role}</small></span></label>{/each}</div></details>{/if}
			{#if preview.available_items?.length}<details open><summary>Approved items · {itemIds.length} selected</summary><div class="choices">{#each preview.available_items as item}<label><input type="checkbox" bind:group={itemIds} value={item.id} /><span>{item.stem}</span></label>{/each}</div></details>{/if}
			<div class="preview-sections"><strong>Output · {preview.document.sections?.length ?? 0} sections</strong>{#each preview.document.sections ?? [] as section}<span>{String((section.header as Record<string, unknown> | undefined)?.title ?? section.section_id ?? 'Section')}</span>{/each}</div>
			<div class="preview-actions"><button class="secondary" type="button" disabled={busy !== null} onclick={() => showPreview(true)}>Refresh selection</button><button class="primary" type="button" disabled={busy !== null || !preview.can_create} onclick={createResource}>{busy === 'create' ? 'Creating…' : 'Create resource'}</button></div>
		</section>
	{/if}
	{#if compositions.length}<section class="saved"><h3>Saved resources</h3>{#each compositions as composition}<article><div><strong>{composition.projection.replaceAll('_', ' ')}</strong><small>{composition.selected_component_refs.length} components · {composition.selected_item_ids.length} items · {composition.template_version}</small></div><div><a href={`/units/${unitId}/resources/${composition.id}`}>Open</a><a href={`/units/${unitId}/resources/${composition.id}?print=true`} target="_blank">Print</a><button type="button" onclick={() => exportResource(composition)}>Export JSON</button></div></article>{/each}</section>{/if}
</section>

<style>
	.resources { max-width: 1180px; margin: 0 auto; }
	.resource-head, .preview > div:first-child, .saved article, .preview-actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
	.resource-head h2, .saved h3 { margin: 0; font: 500 24px Fraunces, Georgia, serif; }
	.resource-head p:last-child { color: var(--ink-2); font-size: 12px; }
	.resource-head > span { border-radius: 999px; background: var(--accent-soft); color: var(--accent); padding: 6px 9px; font-size: 10px; }
	.eyebrow { margin: 0 0 5px; color: var(--ink-3); font: 500 9px 'IBM Plex Mono', monospace; letter-spacing: .1em; text-transform: uppercase; }
	.composer-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 16px; }
	fieldset, .preview, .saved { border: 1px solid var(--rule); border-radius: 9px; background: var(--surface); padding: 14px; }
	legend { color: var(--ink-3); font-size: 10px; font-weight: 600; text-transform: uppercase; }
	fieldset label { display: flex; gap: 7px; margin-top: 7px; font-size: 11px; }
	fieldset small { margin-left: auto; color: var(--amber); }
	fieldset p { color: var(--ink-3); font-size: 10px; }
	.projection-options { display: flex; align-items: center; justify-content: end; gap: 14px; margin-top: 12px; font-size: 11px; }
	.primary, .secondary { border-radius: 7px; padding: 8px 11px; font: 600 11px inherit; }
	.primary { border: 1px solid var(--accent); background: var(--accent); color: white; }
	.secondary { border: 1px solid var(--rule); background: var(--surface); color: var(--ink); }
	.preview { margin-top: 16px; }
	.preview.unavailable { border-color: #dfb294; background: #fff7ed; }
	.preview h3 { margin: 0; text-transform: capitalize; }
	.preview > div[role='alert'], .resource-error { color: #873f30; font-size: 11px; }
	details { border-top: 1px solid var(--rule); margin-top: 12px; padding-top: 10px; }
	summary { cursor: pointer; font-size: 11px; font-weight: 600; }
	.choices { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; margin-top: 8px; }
	.choices label { display: flex; gap: 7px; border-radius: 6px; background: var(--paper); padding: 7px; font-size: 10px; }
	.choices span { display: grid; gap: 2px; }.choices small { color: var(--ink-3); }
	.preview-sections { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; font-size: 10px; }
	.preview-sections span { border-radius: 999px; background: var(--paper); padding: 4px 7px; }
	.preview-actions { justify-content: end; margin-top: 13px; }
	.saved { margin-top: 16px; }.saved article { border-top: 1px solid var(--rule); padding: 10px 0; }.saved article > div:first-child { display: grid; gap: 3px; text-transform: capitalize; }.saved small { color: var(--ink-3); font-size: 9px; }.saved article > div:last-child { display: flex; gap: 6px; }.saved a, .saved button { border: 0; background: none; color: var(--accent); cursor: pointer; font-size: 10px; font-weight: 600; text-decoration: none; }
	@media (max-width: 850px) { .composer-grid { grid-template-columns: repeat(2, 1fr); } }
	@media (max-width: 560px) { .composer-grid, .choices { grid-template-columns: 1fr; }.resource-head { align-items: start; flex-direction: column; }.projection-options { align-items: start; flex-direction: column; } }
</style>
