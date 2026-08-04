<script lang="ts">
	import { browser } from '$app/environment';
	import { dragHandleZone, type DndEvent } from 'svelte-dnd-action';
	import type { BlockInstance } from 'lectio';
	import { mergeAiContentWithEditableFields } from '$lib/builder/components/ai/ai-block-utils';
	import type { DocumentStore } from '$lib/builder/stores/document.svelte';
	import AddSectionControl from './AddSectionControl.svelte';
	import BlockCard from './BlockCard.svelte';
	import SectionDivider from './SectionDivider.svelte';
	import type { PendingPlanSection } from '$lib/builder/streaming/generation-stream';
	import { issuesForSection } from '$lib/builder/issues';
	import type { BuilderIssue } from '$lib/builder/issues';
	import type { V3VisualBlock } from '$lib/api/v3';
	import BuilderVisualIssueAction from './BuilderVisualIssueAction.svelte';
	import {
		qcReasonToInstruction,
		resolveTextIssueTarget,
		resolveVisualIssueTarget
	} from '$lib/builder/issue-targeting';
	import type { BlockAiRepairRequest } from '$lib/builder/issues';
	import { resolveBlockVisual } from '$lib/builder/visual-regeneration';

	let {
		store,
		pendingPlan = [],
		sectionProgress = {},
		generationTerminal = false,
		documentLevelIssues = [],
		onDismissDocumentIssue = () => {},
		generationId = null,
		visualBlocks = [],
		onVisualRegenerated = async () => {}
	}: {
		store: DocumentStore;
		pendingPlan?: PendingPlanSection[];
		sectionProgress?: Record<string, string>;
		generationTerminal?: boolean;
		documentLevelIssues?: BuilderIssue[];
		onDismissDocumentIssue?: (issueId: string) => void;
		generationId?: string | null;
		visualBlocks?: V3VisualBlock[];
		onVisualRegenerated?: () => void | Promise<void>;
	} = $props();

	const readySectionCount = $derived(
		pendingPlan.filter((section) => sectionProgress[section.id] === 'ready').length
	);

	function progressLabel(status: string | undefined): string {
		if (status === 'ready') return 'ready';
		if (status === 'failed') return 'failed';
		return 'writing…';
	}

	const canvasRows = $derived.by(() => {
		const realIds = new Set(store.orderedSections.map((section) => section.id));
		const rows = [
			...store.orderedSections.map((section) => ({ kind: 'section' as const, id: section.id, position: section.position, section })),
			...pendingPlan
				.filter((section) => !generationTerminal && !realIds.has(section.id))
				.map((section) => ({ kind: 'pending' as const, ...section }))
		];
		return rows.sort((left, right) => left.position - right.position);
	});

	let itemsBySection = $state<Record<string, BlockInstance[]>>({});
	let pendingDndMerge: Record<string, BlockInstance[]> = {};
	let rafFlush = 0;
	let aiRepairRequest = $state<BlockAiRepairRequest | null>(null);

	function editIssueBlock(sectionId: string, issue: BuilderIssue): void {
		if (!store.document) return;
		const id = resolveTextIssueTarget(store.document, sectionId, issue);
		if (!id) return;
		store.stopEditing();
		store.selectBlock(id);
		aiRepairRequest = {
			requestKey: `${issue.id}:${Date.now()}`,
			issueId: issue.id,
			sectionId,
			targetBlockId: id,
			initialInstruction: qcReasonToInstruction(issue)
		};
		queueMicrotask(() => globalThis.document.querySelector(`[data-block-id="${id}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
	}

	function reviewIssueSection(sectionId: string): void {
		store.selectSection(sectionId);
		aiRepairRequest = null;
		queueMicrotask(() =>
			globalThis.document
				.getElementById(`section-${sectionId}`)
				?.scrollIntoView({ behavior: 'smooth', block: 'start' })
		);
	}

	function editVisualIssueBlock(sectionId: string, requested?: string): void {
		if (!store.document) return;
		const id = resolveVisualIssueTarget(store.document, sectionId, requested);
		if (!id) return;
		store.selectBlock(id);
		store.startEditing(id);
		queueMicrotask(() => globalThis.document.querySelector(`[data-block-id="${id}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
	}

	$effect(() => {
		const doc = store.document;
		if (!doc) {
			itemsBySection = {};
			return;
		}
		const next: Record<string, BlockInstance[]> = {};
		for (const s of store.orderedSections) {
			next[s.id] = store.blocksForSection(s).map((b) => ({ ...b })) as BlockInstance[];
		}
		itemsBySection = next;
	});

	function scheduleSyncFromDnd(): void {
		if (!browser) return;
		if (rafFlush) cancelAnimationFrame(rafFlush);
		rafFlush = requestAnimationFrame(() => {
			rafFlush = 0;
			const full: Record<string, BlockInstance[]> = {};
			for (const s of store.orderedSections) {
				full[s.id] = pendingDndMerge[s.id] ?? (store.blocksForSection(s) as BlockInstance[]);
			}
			pendingDndMerge = {};
			store.syncSectionsFromDnd(full);
		});
	}

	function handleConsider(sectionId: string, e: CustomEvent<DndEvent<BlockInstance>>): void {
		itemsBySection = { ...itemsBySection, [sectionId]: e.detail.items as BlockInstance[] };
	}

	function handleFinalize(sectionId: string, e: CustomEvent<DndEvent<BlockInstance>>): void {
		const items = e.detail.items as BlockInstance[];
		itemsBySection = { ...itemsBySection, [sectionId]: items };
		pendingDndMerge = { ...pendingDndMerge, [sectionId]: items };
		scheduleSyncFromDnd();
	}

	$effect(() => {
		if (!browser) return;
		const editingId = store.editingBlockId;
		if (!editingId) return;

		function onKey(e: KeyboardEvent): void {
			if (e.key === 'Escape') {
				store.stopEditing();
			}
		}

		function onPointerDown(e: PointerEvent): void {
			const target = e.target;
			if (!(target instanceof Node)) return;
			const inCard = (target as HTMLElement).closest?.(`[data-editing-card="${editingId}"]`);
			if (inCard) return;
			store.stopEditing();
		}

		window.addEventListener('keydown', onKey);
		document.addEventListener('pointerdown', onPointerDown, true);
		return () => {
			window.removeEventListener('keydown', onKey);
			document.removeEventListener('pointerdown', onPointerDown, true);
		};
	});
</script>

<div class="canvas mx-auto w-full max-w-4xl pb-16">
	{#if documentLevelIssues.length > 0}
		<section class="builder-print-hidden mb-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950" aria-label="Lesson review issues">
			{#each documentLevelIssues as issue (issue.id)}
				<div class="flex items-start justify-between gap-3" data-unresolved-issue={issue.id}>
					<div><p class="font-semibold">{issue.kind}</p><p class="mt-1">{issue.message}</p></div>
					<button type="button" class="rounded border border-amber-400 bg-white px-2 py-1 text-xs" onclick={() => onDismissDocumentIssue(issue.id)}>Dismiss</button>
				</div>
			{/each}
		</section>
	{/if}
	{#if pendingPlan.length > 0 && !generationTerminal}
		<p class="builder-print-hidden mb-3 text-sm font-medium text-slate-600" role="status">
			{readySectionCount}/{pendingPlan.length} sections ready
		</p>
	{/if}
	<div class="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-lg shadow-slate-300/25 sm:px-6 sm:py-6">
		{#each canvasRows as row, i (row.id)}
			{#if row.kind === 'pending'}
				<section class="builder-print-hidden mb-4 rounded-xl border border-slate-200 bg-slate-50 p-4" data-testid={`pending-section-${row.id}`}>
					<h2 class="text-base font-semibold text-slate-700">{row.title}</h2>
					<div class="mt-3 rounded-lg border border-dashed border-slate-300 bg-white px-4 py-5 text-sm text-slate-500">
						Generating…
					</div>
				</section>
			{:else}
				{@const section = row.section}
				<AddSectionControl {store} insertIndex={store.orderedSections.indexOf(section)} />
				<SectionDivider {section} {store} isFirstSection={i === 0} />
				{#if pendingPlan.some((planned) => planned.id === section.id) && !generationTerminal}
					<span class="builder-print-hidden mb-2 inline-flex rounded-full border border-slate-300 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-600" data-testid={`section-progress-${section.id}`}>
						{progressLabel(sectionProgress[section.id])}
					</span>
				{/if}
				{#each issuesForSection(section).filter((issue) => !issue.resolved) as issue (issue.id)}
					{@const textRepairTarget = store.document ? resolveTextIssueTarget(store.document, section.id, issue) : undefined}
					{@const visualEditTarget = store.document ? resolveVisualIssueTarget(store.document, section.id, issue.target_block_id) : undefined}
					{@const isVisualIssue = Boolean(issue.visual_id || issue.repair_target_id?.startsWith('visual:'))}
					<div class="builder-print-hidden mb-3 scroll-mt-24 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950" data-unresolved-issue={issue.id}>
						<p class="font-semibold">{issue.severity.toUpperCase()} · {issue.kind}</p>
						<p class="mt-1">{issue.message}</p>
						<div class="mt-2 flex flex-wrap gap-2">
							{#if isVisualIssue}
								{#if visualEditTarget}
									<button type="button" class="rounded border border-amber-400 bg-white px-2 py-1 text-xs" onclick={() => editVisualIssueBlock(section.id, issue.target_block_id)}>Swap image</button>
								{/if}
								<BuilderVisualIssueAction
									{issue}
									{generationId}
									visual={visualBlocks.find((visual) => visual.visual_id === issue.visual_id)}
									onResolved={() => store.resolveIssue(section.id, issue.id)}
									onRegenerated={onVisualRegenerated}
								/>
							{:else if textRepairTarget}
								<button type="button" class="rounded border border-amber-400 bg-white px-2 py-1 text-xs" onclick={() => editIssueBlock(section.id, issue)}>Fix with AI</button>
							{:else}
								<button type="button" class="rounded border border-amber-400 bg-white px-2 py-1 text-xs" onclick={() => reviewIssueSection(section.id)}>Review issue</button>
							{/if}
							<button type="button" class="rounded border border-amber-400 bg-white px-2 py-1 text-xs" onclick={() => store.resolveIssue(section.id, issue.id)}>Dismiss</button>
						</div>
					</div>
				{/each}

				<div
				class="min-h-[2rem]"
				use:dragHandleZone={{
					items: itemsBySection[section.id] ?? [],
					type: 'canvas-block',
					flipDurationMs: 200,
					dropTargetStyle: { outline: '2px dashed #3b82f6' },
					dragDisabled: !!store.editingBlockId
				}}
				onconsider={(e) => handleConsider(section.id, e)}
				onfinalize={(e) => handleFinalize(section.id, e)}
			>
				{#each itemsBySection[section.id] ?? [] as item (item.id)}
					<BlockCard
						block={item}
						sectionId={section.id}
						document={store.document}
						{store}
						selected={store.selectedBlockId === item.id}
						editing={store.editingBlockId === item.id}
						onselect={() => store.selectBlock(item.id)}
						onstartedit={() => store.startEditing(item.id)}
						onstopedit={() => store.stopEditing()}
						onupdatefield={(field, value) => store.updateBlockField(item.id, field, value)}
						onfieldblur={() => store.notifyFieldBlur()}
						contextBlocksForAi={store.getContextBlocksForAi(item.id)}
						{aiRepairRequest}
						onairepairapplied={(request) => {
							store.resolveIssue(request.sectionId, request.issueId);
							aiRepairRequest = null;
						}}
						{generationId}
						matchedVisual={resolveBlockVisual(
							item,
							section.id,
							visualBlocks,
							store.document?.media ?? {}
						)}
						{onVisualRegenerated}
						onapplyaicontent={(content) => {
							const merged = mergeAiContentWithEditableFields(
								item.component_id,
								item.content as Record<string, unknown>,
								content
							);
							store.updateBlockContent(item.id, merged);
							store.startEditing(item.id);
						}}
						onduplicate={() => {
							const nid = store.duplicateBlock(section.id, item.id);
							store.selectBlock(nid);
						}}
						onmoveup={() => store.moveBlock(section.id, section.id, item.id, Math.max(0, section.block_ids.indexOf(item.id) - 1))}
						onmovedown={() => store.moveBlock(section.id, section.id, item.id, Math.min(section.block_ids.length - 1, section.block_ids.indexOf(item.id) + 1))}
						ondelete={() => {
							if (confirm('Remove this block? You can undo.')) {
								store.removeBlock(section.id, item.id);
								const sec = store.document?.sections.find((s) => s.id === section.id);
								if (sec && sec.block_ids.length === 0) {
									if (
										confirm(
											'This section is now empty. Remove the section as well? You can undo.'
										)
									) {
										store.removeSection(section.id);
									}
								}
							}
						}}
					/>
				{/each}
				</div>
			{/if}
		{/each}
		<AddSectionControl {store} insertIndex={store.orderedSections.length} />
	</div>
	<div class="mx-auto mt-4 max-w-3xl rounded-xl border border-slate-200 bg-white/80 px-4 py-2 text-xs text-slate-600">
		Shortcuts:
		<span class="font-medium">Cmd/Ctrl+Z</span> undo,
		<span class="font-medium">Cmd/Ctrl+Shift+Z</span> redo,
		<span class="font-medium">Cmd/Ctrl+S</span> save,
		<span class="font-medium">Cmd/Ctrl+D</span> duplicate,
		<span class="font-medium">Delete</span> remove,
		<span class="font-medium">Esc</span> close editor.
	</div>
</div>
