import type { BlockInstance, DocumentSection, LessonDocument, MediaReference } from 'lectio';
import { getEmptyContent, getTemplateById } from 'lectio';
import { saveDocument } from '$lib/builder/persistence/idb-store';
import {
	ensureBuilderSyncAdapterRegistered,
	flushBuilderSyncQueue,
	saveLessonToServer
} from '$lib/builder/persistence/server-sync';
import { createHistoryStore } from './history.svelte';
import { appendAbsentGenerationSections, type PendingPlanSection } from '$lib/builder/streaming/generation-stream';
import { issuesForSection, type IssueSection } from '$lib/builder/issues';

const FIELD_HISTORY_IDLE_MS = 1000;
const IDB_PERSIST_DEBOUNCE_MS = 300;
const SERVER_PERSIST_DEBOUNCE_MS = 1200;

/** Item row in a canvas DnD zone: real block or palette stub (before materialization). */
export type DndRowItem =
	| BlockInstance
	| { id: string; isPalette: true; component_id: string };

export function isPaletteDndItem(item: DndRowItem): item is { id: string; isPalette: true; component_id: string } {
	return 'isPalette' in item && item.isPalette === true;
}

function collectMediaIdsFromValue(value: unknown, out: Set<string>): void {
	if (value && typeof value === 'object') {
		if (Array.isArray(value)) {
			for (const v of value) collectMediaIdsFromValue(v, out);
			return;
		}
		const o = value as Record<string, unknown>;
		if (typeof o.media_id === 'string' && o.media_id.trim()) out.add(o.media_id);
		for (const v of Object.values(o)) collectMediaIdsFromValue(v, out);
	}
}

function blockIdsReferencingMedia(doc: LessonDocument, mediaId: string): string[] {
	const found: string[] = [];
	for (const [bid, block] of Object.entries(doc.blocks)) {
		const used = new Set<string>();
		collectMediaIdsFromValue(block.content, used);
		if (used.has(mediaId)) found.push(bid);
	}
	return found;
}

function sortSections(sections: DocumentSection[]): DocumentSection[] {
	return [...sections].sort((a, b) => a.position - b.position);
}

function applyBlockPositions(doc: LessonDocument): LessonDocument {
	const blocks = { ...doc.blocks };
	for (const sec of doc.sections) {
		sec.block_ids.forEach((bid, i) => {
			const b = blocks[bid];
			if (b) blocks[bid] = { ...b, position: i };
		});
	}
	return { ...doc, blocks };
}

/**
 * Reactive document store (Svelte 5 runes). Phase 1: load + clear. Phase 2: mutations, selection, undo/redo.
 * Phase 3: composition (add/remove/move blocks and sections), palette target section, flush save.
 */
export function createDocumentStore() {
	let document = $state<LessonDocument | null>(null);
	const history = createHistoryStore(50);

	let selectedBlockId = $state<string | null>(null);
	let editingBlockId = $state<string | null>(null);
	let selectedSectionId = $state<string | null>(null);

	/** True after first field edit in a burst; reset on blur or idle. */
	let fieldBurstOpen = false;
	let fieldIdleTimer: ReturnType<typeof setTimeout> | null = null;

	function clearFieldIdleTimer(): void {
		if (fieldIdleTimer !== null) {
			clearTimeout(fieldIdleTimer);
			fieldIdleTimer = null;
		}
	}

	function scheduleFieldBurstEnd(): void {
		clearFieldIdleTimer();
		fieldIdleTimer = setTimeout(() => {
			fieldBurstOpen = false;
			fieldIdleTimer = null;
		}, FIELD_HISTORY_IDLE_MS);
	}

	function beginFieldMutationIfNeeded(): void {
		if (!document) return;
		if (!fieldBurstOpen) {
			history.pushBeforeMutation(document);
			fieldBurstOpen = true;
		}
	}

	function resetBurstForStructuralMutation(): void {
		fieldBurstOpen = false;
		clearFieldIdleTimer();
	}

	const orderedSections = $derived(
		document ? [...document.sections].sort((a, b) => a.position - b.position) : []
	);

	const canUndo = $derived(history.canUndo);
	const canRedo = $derived(history.canRedo);

	let saveStatus = $state<'saved' | 'saving' | 'error'>('saved');
	let idbPersistTimer: ReturnType<typeof setTimeout> | null = null;
	let serverPersistTimer: ReturnType<typeof setTimeout> | null = null;

	function clearPersistTimers(): void {
		if (idbPersistTimer !== null) {
			clearTimeout(idbPersistTimer);
			idbPersistTimer = null;
		}
		if (serverPersistTimer !== null) {
			clearTimeout(serverPersistTimer);
			serverPersistTimer = null;
		}
	}

	function scheduleIdbPersist(snapshot: LessonDocument): void {
		if (typeof indexedDB === 'undefined') return;
		if (idbPersistTimer !== null) {
			clearTimeout(idbPersistTimer);
		}
		idbPersistTimer = setTimeout(async () => {
			idbPersistTimer = null;
			try {
				await saveDocument(snapshot);
			} catch {
				saveStatus = 'error';
			}
		}, IDB_PERSIST_DEBOUNCE_MS);
	}

	function scheduleServerPersist(snapshot: LessonDocument): void {
		if (serverPersistTimer !== null) {
			clearTimeout(serverPersistTimer);
		}
		serverPersistTimer = setTimeout(async () => {
			serverPersistTimer = null;
			const revision = snapshot.updated_at;
			try {
				await saveLessonToServer(snapshot);
				await flushBuilderSyncQueue();
				if (document?.updated_at === revision) {
					saveStatus = 'saved';
				}
			} catch {
				if (document?.updated_at === revision) {
					saveStatus = 'error';
				}
			}
		}, SERVER_PERSIST_DEBOUNCE_MS);
	}

	function schedulePersist(snapshot: LessonDocument): void {
		saveStatus = 'saving';
		scheduleIdbPersist(snapshot);
		scheduleServerPersist(snapshot);
	}

	function defaultSelectedSection(): void {
		if (!document || document.sections.length === 0) {
			selectedSectionId = null;
			return;
		}
		const sorted = sortSections(document.sections);
		selectedSectionId = sorted[0]!.id;
	}

	function sectionContainingBlock(blockId: string): DocumentSection | undefined {
		if (!document) return undefined;
		return document.sections.find((s) => s.block_ids.includes(blockId));
	}

	function blocksForSection(section: DocumentSection): BlockInstance[] {
		if (!document) return [];
		return section.block_ids.map((id) => document!.blocks[id]).filter(Boolean);
	}

	/** Other blocks in the same section (for AI context), excluding the given block. */
	function getContextBlocksForAi(
		blockId: string
	): Array<{ component_id: string; content: Record<string, unknown> }> {
		if (!document) return [];
		const sec = sectionContainingBlock(blockId);
		if (!sec) return [];
		return blocksForSection(sec)
			.filter((b) => b.id !== blockId)
			.map((b) => ({ component_id: b.component_id, content: { ...b.content } }));
	}

	function updateBlockContent(blockId: string, content: Record<string, unknown>): void {
		if (!document) return;
		const block = document.blocks[blockId];
		if (!block) return;
		history.pushBeforeMutation(document);
		fieldBurstOpen = false;
		clearFieldIdleTimer();
		const next: LessonDocument = {
			...document,
			blocks: {
				...document.blocks,
				[blockId]: { ...block, content }
			},
			updated_at: new Date().toISOString()
		};
		document = next;
		schedulePersist(next);
	}

	function updateBlockField(blockId: string, field: string, value: unknown): void {
		if (!document) return;
		const block = document.blocks[blockId];
		if (!block) return;
		beginFieldMutationIfNeeded();
		const next: LessonDocument = {
			...document,
			blocks: {
				...document.blocks,
				[blockId]: {
					...block,
					content: { ...block.content, [field]: value }
				}
			},
			updated_at: new Date().toISOString()
		};
		document = next;
		scheduleFieldBurstEnd();
		schedulePersist(next);
	}

	function notifyFieldBlur(): void {
		clearFieldIdleTimer();
		fieldBurstOpen = false;
	}

	function selectBlock(id: string): void {
		selectedBlockId = id;
		const sec = sectionContainingBlock(id);
		if (sec) selectedSectionId = sec.id;
	}

	function selectSection(sectionId: string): void {
		selectedSectionId = sectionId;
		selectedBlockId = null;
		editingBlockId = null;
	}

	function startEditing(id: string): void {
		editingBlockId = id;
		selectedBlockId = id;
		const sec = sectionContainingBlock(id);
		if (sec) selectedSectionId = sec.id;
	}

	function stopEditing(): void {
		editingBlockId = null;
		clearFieldIdleTimer();
		fieldBurstOpen = false;
	}

	function undo(): void {
		if (!document) return;
		const prev = history.undo(document);
		if (prev) {
			document = prev;
			clearFieldIdleTimer();
			fieldBurstOpen = false;
			schedulePersist(prev);
		}
	}

	function redo(): void {
		if (!document) return;
		const next = history.redo(document);
		if (next) {
			document = next;
			clearFieldIdleTimer();
			fieldBurstOpen = false;
			schedulePersist(next);
		}
	}

	function addBlock(sectionId: string, componentId: string, position?: number): string {
		if (!document) return '';
		const section = document.sections.find((s) => s.id === sectionId);
		if (!section) return '';
		history.pushBeforeMutation(document);
		resetBurstForStructuralMutation();
		const blockId = crypto.randomUUID();
		const blockIds = [...section.block_ids];
		const idx = position === undefined ? blockIds.length : Math.max(0, Math.min(position, blockIds.length));
		blockIds.splice(idx, 0, blockId);
		const newBlock: BlockInstance = {
			id: blockId,
			component_id: componentId,
			content: getEmptyContent(componentId),
			position: idx
		};
		const sections = document.sections.map((s) =>
			s.id === sectionId ? { ...s, block_ids: blockIds } : s
		);
		let next: LessonDocument = {
			...document,
			sections,
			blocks: { ...document.blocks, [blockId]: newBlock },
			updated_at: new Date().toISOString()
		};
		next = applyBlockPositions(next);
		document = next;
		schedulePersist(next);
		return blockId;
	}

	function removeBlock(sectionId: string, blockId: string): void {
		if (!document) return;
		const section = document.sections.find((s) => s.id === sectionId);
		if (!section || !section.block_ids.includes(blockId)) return;
		history.pushBeforeMutation(document);
		resetBurstForStructuralMutation();
		const block_ids = section.block_ids.filter((id) => id !== blockId);
		const { [blockId]: _removed, ...restBlocks } = document.blocks;
		const sections = document.sections.map((s) => (s.id === sectionId ? { ...s, block_ids } : s));
		let next: LessonDocument = {
			...document,
			sections,
			blocks: restBlocks,
			updated_at: new Date().toISOString()
		};
		next = applyBlockPositions(next);
		document = next;
		if (selectedBlockId === blockId) selectedBlockId = null;
		if (editingBlockId === blockId) editingBlockId = null;
		schedulePersist(next);
	}

	function duplicateBlock(sectionId: string, blockId: string): string {
		if (!document) return '';
		const section = document.sections.find((s) => s.id === sectionId);
		const block = document.blocks[blockId];
		if (!section || !block || !section.block_ids.includes(blockId)) return '';
		history.pushBeforeMutation(document);
		resetBurstForStructuralMutation();
		const clone = JSON.parse(JSON.stringify(block)) as BlockInstance;
		const newId = crypto.randomUUID();
		clone.id = newId;
		const idx = section.block_ids.indexOf(blockId);
		const block_ids = [...section.block_ids];
		block_ids.splice(idx + 1, 0, newId);
		const sections = document.sections.map((s) => (s.id === sectionId ? { ...s, block_ids } : s));
		let next: LessonDocument = {
			...document,
			sections,
			blocks: { ...document.blocks, [newId]: { ...clone, position: idx + 1 } },
			updated_at: new Date().toISOString()
		};
		next = applyBlockPositions(next);
		document = next;
		schedulePersist(next);
		return newId;
	}

	function moveBlock(
		sourceSectionId: string,
		targetSectionId: string,
		blockId: string,
		targetPosition: number
	): void {
		if (!document) return;
		const source = document.sections.find((s) => s.id === sourceSectionId);
		const target = document.sections.find((s) => s.id === targetSectionId);
		if (!source || !target || !source.block_ids.includes(blockId)) return;
		history.pushBeforeMutation(document);
		resetBurstForStructuralMutation();

		let sections: DocumentSection[];

		if (sourceSectionId === targetSectionId) {
			const ids = [...source.block_ids];
			const from = ids.indexOf(blockId);
			if (from === -1) return;
			ids.splice(from, 1);
			const insertAt = Math.max(0, Math.min(targetPosition, ids.length));
			ids.splice(insertAt, 0, blockId);
			sections = document.sections.map((s) => (s.id === sourceSectionId ? { ...s, block_ids: ids } : s));
		} else {
			const sourceIds = source.block_ids.filter((id) => id !== blockId);
			const targetIds = [...target.block_ids];
			const insertAt = Math.max(0, Math.min(targetPosition, targetIds.length));
			targetIds.splice(insertAt, 0, blockId);
			sections = document.sections.map((s) => {
				if (s.id === sourceSectionId) return { ...s, block_ids: sourceIds };
				if (s.id === targetSectionId) return { ...s, block_ids: targetIds };
				return s;
			});
		}

		let next: LessonDocument = {
			...document,
			sections,
			updated_at: new Date().toISOString()
		};
		next = applyBlockPositions(next);
		document = next;
		schedulePersist(next);
	}

	function addSection(templateId: string, position?: number, titleOverride?: string): string {
		if (!document) return '';
		const def = getTemplateById(templateId);
		if (!def) return '';
		history.pushBeforeMutation(document);
		resetBurstForStructuralMutation();
		const always = def.contract.always_present;
		const blockIds: string[] = [];
		const newBlocks: Record<string, BlockInstance> = { ...document.blocks };
		for (let i = 0; i < always.length; i++) {
			const cid = always[i]!;
			const bid = crypto.randomUUID();
			blockIds.push(bid);
			newBlocks[bid] = {
				id: bid,
				component_id: cid,
				content: getEmptyContent(cid),
				position: i
			};
		}
		const sectionId = crypto.randomUUID();
		const sorted = sortSections(document.sections);
		const insertAt = position === undefined ? sorted.length : Math.max(0, Math.min(position, sorted.length));
		const newSection: DocumentSection = {
			id: sectionId,
			template_id: templateId,
			title: titleOverride?.trim() || def.contract.name,
			position: insertAt,
			block_ids: blockIds
		};
		const reordered = [...sorted.slice(0, insertAt), newSection, ...sorted.slice(insertAt)].map((s, i) => ({
			...s,
			position: i
		}));
		let next: LessonDocument = {
			...document,
			sections: reordered,
			blocks: newBlocks,
			updated_at: new Date().toISOString()
		};
		next = applyBlockPositions(next);
		document = next;
		schedulePersist(next);
		return sectionId;
	}

	function removeSection(sectionId: string): void {
		if (!document) return;
		const section = document.sections.find((s) => s.id === sectionId);
		if (!section) return;
		history.pushBeforeMutation(document);
		resetBurstForStructuralMutation();
		const toRemove = new Set(section.block_ids);
		const blocks = { ...document.blocks };
		for (const id of toRemove) delete blocks[id];
		const remaining = document.sections
			.filter((s) => s.id !== sectionId)
			.sort((a, b) => a.position - b.position)
			.map((s, i) => ({ ...s, position: i }));
		let next: LessonDocument = {
			...document,
			sections: remaining,
			blocks,
			updated_at: new Date().toISOString()
		};
		next = applyBlockPositions(next);
		document = next;
		if (selectedSectionId === sectionId) defaultSelectedSection();
		if (selectedBlockId && toRemove.has(selectedBlockId)) selectedBlockId = null;
		if (editingBlockId && toRemove.has(editingBlockId)) editingBlockId = null;
		schedulePersist(next);
	}

	function reorderSections(orderedIds: string[]): void {
		if (!document) return;
		const map = new Map(document.sections.map((s) => [s.id, s]));
		const nextSections: DocumentSection[] = [];
		for (let i = 0; i < orderedIds.length; i++) {
			const id = orderedIds[i]!;
			const s = map.get(id);
			if (s) nextSections.push({ ...s, position: i });
		}
		if (nextSections.length !== document.sections.length) return;
		history.pushBeforeMutation(document);
		resetBurstForStructuralMutation();
		let next: LessonDocument = {
			...document,
			sections: nextSections,
			updated_at: new Date().toISOString()
		};
		document = next;
		schedulePersist(next);
	}

	function updateSectionTitle(sectionId: string, title: string): void {
		if (!document) return;
		history.pushBeforeMutation(document);
		resetBurstForStructuralMutation();
		const sections = document.sections.map((s) =>
			s.id === sectionId ? { ...s, title } : s
		);
		const next: LessonDocument = {
			...document,
			sections,
			updated_at: new Date().toISOString()
		};
		document = next;
		schedulePersist(next);
	}

	function resolveIssue(sectionId: string, issueId: string): void {
		if (!document) return;
		const section = document.sections.find((item) => item.id === sectionId);
		if (!section || !issuesForSection(section).some((issue) => issue.id === issueId && !issue.resolved)) return;
		history.pushBeforeMutation(document);
		const sections = document.sections.map((item) => item.id === sectionId
			? ({ ...item, meta: { ...(item as IssueSection).meta, issues: issuesForSection(item).map((issue) => issue.id === issueId ? { ...issue, resolved: true } : issue) } } as IssueSection)
			: item);
		document = { ...document, sections, updated_at: new Date().toISOString() };
		schedulePersist(document);
	}

	/**
	 * Apply per-section DnD rows in one history step (cross-section moves + palette inserts).
	 * Each section id in the map must exist; omitted sections keep current block_ids.
	 */
	function syncSectionsFromDnd(layout: Record<string, DndRowItem[]>): void {
		if (!document) return;
		history.pushBeforeMutation(document);
		resetBurstForStructuralMutation();

		let blocks = { ...document.blocks };
		const nextSections = document.sections.map((sec) => {
			const row = layout[sec.id];
			if (!row) return sec;
			const newBlockIds: string[] = [];
			for (let i = 0; i < row.length; i++) {
				const item = row[i]!;
				if (isPaletteDndItem(item)) {
					const bid = crypto.randomUUID();
					const cid = item.component_id;
					newBlockIds.push(bid);
					blocks[bid] = {
						id: bid,
						component_id: cid,
						content: getEmptyContent(cid),
						position: i
					};
				} else {
					newBlockIds.push(item.id);
					blocks[item.id] = { ...item, position: i };
				}
			}
			return { ...sec, block_ids: newBlockIds };
		});

		const used = new Set(nextSections.flatMap((s) => s.block_ids));
		blocks = Object.fromEntries(Object.entries(blocks).filter(([id]) => used.has(id)));

		let next: LessonDocument = {
			...document,
			sections: nextSections,
			blocks,
			updated_at: new Date().toISOString()
		};
		next = applyBlockPositions(next);
		document = next;
		schedulePersist(next);
	}

	async function flushSave(): Promise<void> {
		if (!document) return;
		clearPersistTimers();
		saveStatus = 'saving';
		let idbFailed = false;
		try {
			await saveDocument(document);
		} catch {
			idbFailed = true;
		}
		try {
			await saveLessonToServer(document);
			await flushBuilderSyncQueue();
			saveStatus = idbFailed ? 'error' : 'saved';
		} catch {
			saveStatus = 'error';
		}
	}

	function deselectBlock(): void {
		selectedBlockId = null;
	}

	function getSectionIdForBlock(blockId: string): string | null {
		return sectionContainingBlock(blockId)?.id ?? null;
	}

	function addMedia(media: MediaReference): void {
		if (!document) return;
		history.pushBeforeMutation(document);
		resetBurstForStructuralMutation();
		const next: LessonDocument = {
			...document,
			media: { ...document.media, [media.id]: media },
			updated_at: new Date().toISOString()
		};
		document = next;
		schedulePersist(next);
	}

	function updateMedia(mediaId: string, updates: Partial<MediaReference>): void {
		if (!document) return;
		const existing = document.media[mediaId];
		if (!existing) return;
		history.pushBeforeMutation(document);
		resetBurstForStructuralMutation();
		const next: LessonDocument = {
			...document,
			media: { ...document.media, [mediaId]: { ...existing, ...updates } },
			updated_at: new Date().toISOString()
		};
		document = next;
		schedulePersist(next);
	}

	function removeMedia(mediaId: string): void {
		if (!document) return;
		const usage = blockIdsReferencingMedia(document, mediaId);
		if (usage.length > 0) {
			throw new Error(`Media is used by ${usage.length} block(s); remove references first.`);
		}
		if (!document.media[mediaId]) return;
		history.pushBeforeMutation(document);
		resetBurstForStructuralMutation();
		const { [mediaId]: _removed, ...restMedia } = document.media;
		const next: LessonDocument = {
			...document,
			media: restMedia,
			updated_at: new Date().toISOString()
		};
		document = next;
		schedulePersist(next);
	}

	function getMediaUsage(mediaId: string): string[] {
		if (!document) return [];
		return blockIdsReferencingMedia(document, mediaId);
	}

	function insertSectionsFromGeneration(adapted: LessonDocument, plan: PendingPlanSection[]): boolean {
		if (!document) return false;
		const next = appendAbsentGenerationSections(document, adapted, plan);
		if (next === document) return false;
		document = next;
		if (!selectedSectionId) defaultSelectedSection();
		schedulePersist(next);
		return true;
	}

	return {
		get document() {
			return document;
		},
		get orderedSections() {
			return orderedSections;
		},
		get selectedBlockId() {
			return selectedBlockId;
		},
		get editingBlockId() {
			return editingBlockId;
		},
		get selectedSectionId() {
			return selectedSectionId;
		},
		get canUndo() {
			return canUndo;
		},
		get canRedo() {
			return canRedo;
		},
		get saveStatus() {
			return saveStatus;
		},
		blocksForSection,
		getContextBlocksForAi,
		loadDocument(doc: LessonDocument) {
			ensureBuilderSyncAdapterRegistered();
			document = doc;
			history.clear();
			selectedBlockId = null;
			editingBlockId = null;
			fieldBurstOpen = false;
			clearFieldIdleTimer();
			clearPersistTimers();
			saveStatus = 'saved';
			void flushBuilderSyncQueue();
			defaultSelectedSection();
		},
		clear() {
			document = null;
			history.clear();
			selectedBlockId = null;
			editingBlockId = null;
			selectedSectionId = null;
			fieldBurstOpen = false;
			clearFieldIdleTimer();
			clearPersistTimers();
			saveStatus = 'saved';
		},
		updateBlockContent,
		updateBlockField,
		notifyFieldBlur,
		selectBlock,
		selectSection,
		startEditing,
		stopEditing,
		undo,
		redo,
		addBlock,
		removeBlock,
		duplicateBlock,
		moveBlock,
		addSection,
		removeSection,
		reorderSections,
		updateSectionTitle,
		resolveIssue,
		syncSectionsFromDnd,
		flushSave,
		deselectBlock,
		getSectionIdForBlock,
		addMedia,
		updateMedia,
		removeMedia,
		getMediaUsage,
		insertSectionsFromGeneration
	};
}

export type DocumentStore = ReturnType<typeof createDocumentStore>;
