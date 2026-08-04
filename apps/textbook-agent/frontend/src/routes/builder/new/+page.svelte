<script lang="ts">
	import { goto } from '$app/navigation';
	import type { BlockInstance, LessonDocument } from 'lectio';
	import {
		basePresets,
		getEmptyContent,
		getTemplateById,
		templateRegistry
	} from 'lectio';
	import { createBuilderLesson } from '$lib/builder/api/lesson-crud';
	import { saveDocument } from '$lib/builder/persistence/idb-store';

	let title = $state('');
	let subject = $state('');
	let templateId = $state(templateRegistry[0]?.contract.id ?? 'open-canvas');
	let presetId = $state(basePresets[0]?.id ?? 'blue-classroom');
	let createError = $state<string | null>(null);

	const presetChoices = $derived.by(() => {
		const def = getTemplateById(templateId);
		if (!def) return basePresets;
		const allowed = new Set(def.contract.allowedPresets);
		return basePresets.filter((p) => allowed.has(p.id));
	});

	$effect(() => {
		const list = presetChoices;
		if (list.length > 0 && !list.some((p) => p.id === presetId)) {
			presetId = list[0]!.id;
		}
	});

	function createFromTemplate(
		lessonTitle: string,
		lessonSubject: string,
		tmplId: string,
		preset: string
	): LessonDocument {
		const template = getTemplateById(tmplId);
		if (!template) throw new Error(`Unknown template: ${tmplId}`);
		const contract = template.contract;
		const blocks: Record<string, BlockInstance> = {};
		const blockIds: string[] = [];
		for (const componentId of contract.always_present) {
			const blockId = crypto.randomUUID();
			blocks[blockId] = {
				id: blockId,
				component_id: componentId,
				content: getEmptyContent(componentId),
				position: blockIds.length
			};
			blockIds.push(blockId);
		}
		const t = lessonTitle.trim() || 'Untitled lesson';
		return {
			version: 1,
			id: crypto.randomUUID(),
			title: t,
			subject: lessonSubject.trim() || 'general',
			preset_id: preset,
			source: 'template',
			sections: [
				{
					id: crypto.randomUUID(),
					template_id: tmplId,
					block_ids: blockIds,
					title: t,
					position: 0
				}
			],
			blocks,
			media: {},
			created_at: new Date().toISOString(),
			updated_at: new Date().toISOString()
		};
	}

	function createBlank(lessonTitle: string, lessonSubject: string, preset: string): LessonDocument {
		const t = lessonTitle.trim() || 'Untitled lesson';
		const sectionId = crypto.randomUUID();
		return {
			version: 1,
			id: crypto.randomUUID(),
			title: t,
			subject: lessonSubject.trim() || 'general',
			preset_id: preset,
			source: 'manual',
			sections: [
				{
					id: sectionId,
					template_id: 'open-canvas',
					block_ids: [],
					title: t,
					position: 0
				}
			],
			blocks: {},
			media: {},
			created_at: new Date().toISOString(),
			updated_at: new Date().toISOString()
		};
	}

	async function onCreateFromTemplate(): Promise<void> {
		createError = null;
		const doc = createFromTemplate(title, subject, templateId, presetId);
		try {
			const created = await createBuilderLesson({
				source_type: 'template',
				title: doc.title,
				document: doc
			});
			await saveDocument(created.document);
			await goto(`/builder/${created.id}`);
		} catch (error) {
			createError = error instanceof Error ? error.message : 'Failed to create lesson.';
		}
	}

	async function onStartBlank(): Promise<void> {
		createError = null;
		const doc = createBlank(title, subject, presetId);
		try {
			const created = await createBuilderLesson({
				source_type: 'manual',
				title: doc.title,
				document: doc
			});
			await saveDocument(created.document);
			await goto(`/builder/${created.id}`);
		} catch (error) {
			createError = error instanceof Error ? error.message : 'Failed to create lesson.';
		}
	}
</script>

<div class="mx-auto max-w-2xl p-8">
	<h1 class="mb-2 text-2xl font-bold text-slate-900">New lesson</h1>
	<p class="mb-8 text-sm text-slate-600">
		Start from a template scaffold or a blank canvas. You can change content anytime in the builder.
	</p>

	<div class="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
		{#if createError}
			<p class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
				{createError}
			</p>
		{/if}
		<div>
			<label class="mb-1 block text-sm font-medium text-slate-700" for="nl-title">Lesson title</label>
			<input
				id="nl-title"
				class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
				bind:value={title}
				placeholder="e.g. Introduction to fractions"
				data-testid="new-lesson-title"
			/>
		</div>
		<div>
			<label class="mb-1 block text-sm font-medium text-slate-700" for="nl-subject">Subject</label>
			<input
				id="nl-subject"
				class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
				bind:value={subject}
				placeholder="e.g. mathematics"
				data-testid="new-lesson-subject"
			/>
		</div>
		<div>
			<label class="mb-1 block text-sm font-medium text-slate-700" for="nl-template">Template</label>
			<select
				id="nl-template"
				class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
				bind:value={templateId}
				data-testid="new-lesson-template"
			>
				{#each templateRegistry as def (def.contract.id)}
					<option value={def.contract.id}>{def.contract.name}</option>
				{/each}
			</select>
		</div>
		<div>
			<label class="mb-1 block text-sm font-medium text-slate-700" for="nl-preset">Preset</label>
			<select
				id="nl-preset"
				class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
				bind:value={presetId}
				data-testid="new-lesson-preset"
			>
				{#each presetChoices as p (p.id)}
					<option value={p.id}>{p.name}</option>
				{/each}
			</select>
		</div>

		<div class="flex flex-wrap gap-3 pt-2">
			<button
				type="button"
				class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
				data-testid="new-lesson-create"
				onclick={() => void onCreateFromTemplate()}
			>
				Create from template
			</button>
			<button
				type="button"
				class="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50"
				data-testid="new-lesson-blank"
				onclick={() => void onStartBlank()}
			>
				Start blank
			</button>
			<a href="/" class="self-center text-sm font-medium text-blue-600 hover:text-blue-800">Cancel</a>
		</div>
	</div>
</div>
