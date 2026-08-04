<script lang="ts">
	import { dragHandle } from 'svelte-dnd-action';
	import { cn } from 'lectio';
	import { getComponentById, getEditSchema } from 'lectio';
	import type { BlockInstance, LessonDocument } from 'lectio';
	import type { DocumentStore } from '$lib/builder/stores/document.svelte';
	import { ArrowDown, ArrowUp, Copy, GripVertical, Pencil, Trash2 } from 'lucide-svelte';
	import type { BlockGenerateContextBlock } from '$lib/builder/api/ai-client';
	import type { V3VisualBlock } from '$lib/api/v3';
	import { apiBaseUrl } from '$lib/builder/api/public-env';
	import AiBlockAssist from '$lib/builder/components/ai/AiBlockAssist.svelte';
	import { isAiGeneratableComponent } from '$lib/builder/components/ai/ai-block-utils';
	import type { BlockAiRepairRequest } from '$lib/builder/issues';
	import { getToken } from '$lib/stores/auth';
	import { saveVersionSnapshot } from '$lib/builder/persistence/idb-store';
	import { validationWarningsForBlock } from '$lib/builder/utils/section-validation';
	import { isTextEditingTarget } from '$lib/builder/utils/shortcuts';
	import BlockEditor from './BlockEditor.svelte';
	import BlockPreview from './BlockPreview.svelte';
	import VisualRegeneratePopover from './VisualRegeneratePopover.svelte';
	import { isSingleAssetVisualBlock } from '$lib/builder/visual-regeneration';

	let {
		block,
		document,
		sectionId,
		store,
		selected = false,
		editing = false,
		onselect,
		onstartedit,
		onstopedit,
		onupdatefield,
		onfieldblur,
		onduplicate,
		onmoveup,
		onmovedown,
		ondelete,
		contextBlocksForAi = [],
		onapplyaicontent,
		aiRepairRequest = null,
		onairepairapplied,
		generationId = null,
		matchedVisual,
		onVisualRegenerated = async () => {}
	}: {
		block: BlockInstance;
		document: LessonDocument | null;
		sectionId?: string;
		store: DocumentStore;
		selected?: boolean;
		editing?: boolean;
		onselect?: () => void;
		onstartedit?: () => void;
		onstopedit?: () => void;
		onupdatefield?: (field: string, value: unknown) => void;
		onfieldblur?: () => void;
		onduplicate?: () => void;
		onmoveup?: () => void;
		onmovedown?: () => void;
		ondelete?: () => void;
		contextBlocksForAi?: BlockGenerateContextBlock[];
		onapplyaicontent?: (content: Record<string, unknown>) => void;
		aiRepairRequest?: BlockAiRepairRequest | null;
		onairepairapplied?: (request: BlockAiRepairRequest) => void | Promise<void>;
		generationId?: string | null;
		matchedVisual?: V3VisualBlock;
		onVisualRegenerated?: () => void | Promise<void>;
	} = $props();

	const apiConfigured = $derived(Boolean(apiBaseUrl()));
	const aiGradeBand = $derived(document?.grade_band ?? 'secondary');
	const aiToken = $derived(getToken());

	const meta = $derived(getComponentById(block.component_id));
	const editSchema = $derived(getEditSchema(block.component_id));

	let sectionWarnings = $state<string[]>([]);

	let lastEditing = false;
	$effect(() => {
		if (lastEditing && !editing && document) {
			sectionWarnings = validationWarningsForBlock(document, block.id);
		}
		lastEditing = editing;
	});

	function handleStopEdit(): void {
		onstopedit?.();
	}

	async function snapshotBeforeAi(): Promise<void> {
		if (!document) return;
		await saveVersionSnapshot(document.id, document, 'Before AI generation');
	}
</script>

<div
	class={cn(
		'block-card relative mb-6 rounded-xl border border-slate-200 bg-white shadow-sm outline-none',
		selected && 'ring-2 ring-blue-500'
	)}
	data-block-id={block.id}
	data-component-id={block.component_id}
	data-testid="block-card"
	data-editing-card={editing ? block.id : undefined}
	role="button"
	tabindex="0"
	onclick={(e) => {
		const t = e.target as HTMLElement;
		if (
			t.closest?.('.drag-handle') ||
			t.closest?.('button') ||
			t.closest?.('[data-visual-regenerate-root]')
		)
			return;
		onselect?.();
	}}
	ondblclick={(e) => {
		const t = e.target as HTMLElement;
		if (t.closest?.('.drag-handle') || t.closest?.('[data-visual-regenerate-root]')) return;
		onstartedit?.();
	}}
	onkeydown={(e) => {
		if (e.key === 'Enter' || e.key === ' ') {
			const t = e.target as HTMLElement;
			if (t.closest?.('button')) return;
			if (isTextEditingTarget(t)) return;
			e.preventDefault();
			onselect?.();
		}
	}}
>
	{#if selected && !editing}
		<span
			class="drag-handle absolute -left-3 top-1/2 z-10 inline-flex -translate-y-1/2 cursor-grab touch-none rounded-full border border-slate-200 bg-white p-1.5 text-slate-500 shadow-sm hover:bg-slate-50 hover:text-slate-700 active:cursor-grabbing"
			aria-label="Drag to reorder"
			data-testid="block-drag-handle"
			role="presentation"
			onpointerdown={(e) => e.stopPropagation()}
			use:dragHandle
		>
			<GripVertical size={14} aria-hidden="true" />
		</span>
	{/if}
	<div
		class="block-card-chrome flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-2"
	>
		<div class="flex min-w-0 flex-1 items-center gap-2">
			<span
				class="block-label truncate text-xs font-semibold uppercase tracking-wide text-slate-500"
			>
				{meta?.teacherLabel ?? block.component_id}
			</span>
		</div>
		<div class="flex flex-wrap items-center gap-1">
			{#if editing}
				<button
					type="button"
					class="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
					onclick={(e) => {
						e.stopPropagation();
						handleStopEdit();
					}}
				>
					Close
				</button>
			{:else if editSchema && !selected}
				<button
					type="button"
					class="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
					onclick={(e) => {
						e.stopPropagation();
						onstartedit?.();
					}}
				>
					Edit
				</button>
			{/if}
		</div>
	</div>

	{#if selected && !editing}
		<div class="absolute right-3 top-3 z-10 flex items-center gap-1 rounded-lg border border-slate-200 bg-white/95 p-1 shadow">
			{#if isSingleAssetVisualBlock(block.component_id)}
				<VisualRegeneratePopover
					presentation="popover"
					{generationId}
					visual={matchedVisual}
					onRegenerated={onVisualRegenerated}
				/>
			{/if}
			{#if editSchema && onapplyaicontent && isAiGeneratableComponent(block.component_id)}
				<AiBlockAssist
					{block}
					lessonId={document?.id}
					{sectionId}
					subject={document?.subject ?? ''}
					gradeBand={aiGradeBand}
					contextBlocks={contextBlocksForAi}
					token={aiToken}
					{apiConfigured}
					onBeforeGenerate={snapshotBeforeAi}
					ongenerated={onapplyaicontent}
					repairRequest={aiRepairRequest}
					onRepairApplied={onairepairapplied}
				/>
			{/if}
			{#if editSchema}
				<button
					type="button"
					class="rounded-md p-1.5 text-slate-600 hover:bg-slate-100"
					title="Edit"
					aria-label="Edit"
					onclick={(e) => {
						e.stopPropagation();
						onstartedit?.();
					}}
				>
					<Pencil size={16} />
				</button>
			{/if}
			<button
				type="button" class="rounded-md p-1.5 text-slate-600 hover:bg-slate-100" title="Move up" aria-label="Move up"
				onclick={(e) => { e.stopPropagation(); onmoveup?.(); }}><ArrowUp size={16} /></button>
			<button
				type="button" class="rounded-md p-1.5 text-slate-600 hover:bg-slate-100" title="Move down" aria-label="Move down"
				onclick={(e) => { e.stopPropagation(); onmovedown?.(); }}><ArrowDown size={16} /></button>
			<button
				type="button"
				class="rounded-md p-1.5 text-slate-600 hover:bg-slate-100"
				title="Duplicate"
				aria-label="Duplicate"
				onclick={(e) => {
					e.stopPropagation();
					onduplicate?.();
				}}
			>
				<Copy size={16} />
			</button>
			<button
				type="button"
				class="rounded-md p-1.5 text-red-600 hover:bg-red-50"
				title="Delete"
				aria-label="Delete"
				onclick={(e) => {
					e.stopPropagation();
					ondelete?.();
				}}
			>
				<Trash2 size={16} />
			</button>
		</div>
	{/if}

	{#if editing && editSchema}
		<div class="flex flex-col gap-4 p-2 lg:grid lg:grid-cols-2 lg:gap-4 lg:p-4">
			<div class="min-w-0 border-slate-100 lg:border-r lg:pr-4">
				<BlockEditor
					schema={editSchema}
					content={block.content}
					onchange={(field, value) => onupdatefield?.(field, value)}
					onfieldblur={onfieldblur}
					{store}
				/>
			</div>
			<div class="min-w-0 overflow-hidden rounded-lg border border-slate-100 bg-slate-50/50 p-3" style="overflow-wrap: break-word; word-break: break-word;">
				<p class="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Live preview</p>
				<BlockPreview
					componentId={block.component_id}
					content={block.content}
					media={document?.media ?? {}}
				/>
			</div>
	</div>
	{:else}
		<div class="block-content overflow-hidden p-4" style="overflow-wrap: break-word; word-break: break-word;">
			<BlockPreview
				componentId={block.component_id}
				content={block.content}
				media={document?.media ?? {}}
			/>
		</div>
	{/if}

	{#if sectionWarnings.length > 0}
		<details class="border-t border-amber-100 bg-amber-50/50 px-4 py-2 text-sm text-amber-900">
			<summary class="cursor-pointer font-medium">Section validation ({sectionWarnings.length})</summary>
			<ul class="mt-2 list-inside list-disc space-y-1 text-xs">
				{#each sectionWarnings as w (w)}
					<li>{w}</li>
				{/each}
			</ul>
		</details>
	{/if}
</div>
