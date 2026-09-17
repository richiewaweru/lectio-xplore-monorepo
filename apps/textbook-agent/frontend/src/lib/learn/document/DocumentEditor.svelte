<script lang="ts">
	/**
	 * LearnDocument v2 authoring surface: edit / add / delete / reorder / save / reload / preview.
	 * Uses the canonical LearnDocument — not a separate editor-only model.
	 */
	import {
		DOCUMENT_PRIMITIVE_KINDS,
		isLearnDocument,
		type LearnDocument
	} from './types';
	import type { AddableKind } from './document-state';
	import { createLearnDocumentStore } from './document-state.svelte';
	import DocumentCanvas from './DocumentCanvas.svelte';
	import {
		getBuilderLesson,
		updateBuilderLesson
	} from '$lib/learn/authoring/builder/api/lesson-crud';

	const INTERACTION_KINDS = [
		'choice',
		'multi-select',
		'fill-blank',
		'numeric',
		'short-response',
		'match-pairs',
		'classify',
		'sequence'
	] as const;

	interface Props {
		document: LearnDocument;
		lessonId?: string | null;
		previewHref?: string | null;
		onDocumentChange?: (doc: LearnDocument) => void;
		hideChromeActions?: boolean;
	}

	let {
		document: initialDocument,
		lessonId = null,
		previewHref = null,
		onDocumentChange = undefined,
		hideChromeActions = false
	}: Props = $props();

	const store = createLearnDocumentStore();
	store.loadDocument(initialDocument);

	let status = $state<string | null>(null);
	let saving = $state(false);
	let addKind = $state<AddableKind>('paragraph');
	let activeSectionId = $state<string>('all');

	$effect(() => {
		if (store.document) onDocumentChange?.(store.document);
	});

	const doc = $derived(store.document);
	const selectedId = $derived(store.selectedNodeId);
	const sections = $derived(doc?.sections ?? []);
	const viewDocument = $derived.by(() => {
		if (!doc || activeSectionId === 'all' || sections.length === 0) return doc;
		const section = sections.find((item) => item.id === activeSectionId);
		const allowed = new Set(section?.node_ids ?? []);
		return { ...doc, nodes: doc.nodes.filter((node) => allowed.has(node.id)) };
	});

	async function save() {
		if (!doc || !lessonId) {
			status = lessonId ? null : 'No lesson id — local edit only';
			if (!lessonId && doc) {
				store.markClean();
				status = 'Saved locally';
			}
			return;
		}
		saving = true;
		status = null;
		try {
			await updateBuilderLesson(lessonId, {
				title: doc.title,
				document: doc
			});
			store.markClean();
			status = 'Saved';
		} catch (err) {
			status = err instanceof Error ? err.message : 'Save failed';
		} finally {
			saving = false;
		}
	}

	async function reload() {
		if (!lessonId) {
			status = 'No lesson id to reload';
			return;
		}
		status = null;
		try {
			const record = await getBuilderLesson(lessonId);
			if (!isLearnDocument(record.document)) {
				status = 'Server document is not LearnDocument v2';
				return;
			}
			store.loadDocument(record.document);
			status = 'Reloaded';
		} catch (err) {
			status = err instanceof Error ? err.message : 'Reload failed';
		}
	}

	function addSelectedKind() {
		if (!doc) return;
		store.addNode(addKind, selectedId);
	}
</script>

{#if doc}
	<div class="document-editor" data-testid="document-editor" data-dirty={store.dirty ? 'true' : 'false'}>
		<div class="layout">
			<aside class="palette" aria-label="Add content">
				<p class="palette-title">Content</p>
				{#each DOCUMENT_PRIMITIVE_KINDS as kind}
					<button
						type="button"
						class="palette-item"
						class:active={addKind === kind}
						onclick={() => {
							addKind = kind;
							store.addNode(kind, selectedId);
						}}
					>
						{kind}
					</button>
				{/each}
				<p class="palette-title">Interactions</p>
				<p class="palette-hint">Select an interaction on the canvas to edit prompts and answers.</p>
				<ul class="ix-list">
					{#each INTERACTION_KINDS as kind}
						<li>{kind.replaceAll('-', ' ')}</li>
					{/each}
				</ul>
			</aside>

			<div class="main">
				<header class="toolbar">
					<div class="group">
						<button type="button" data-testid="editor-add" onclick={addSelectedKind}>Add {addKind}</button>
						<button
							type="button"
							data-testid="editor-delete"
							disabled={!selectedId}
							onclick={() => selectedId && store.deleteNode(selectedId)}
						>
							Delete
						</button>
						<button
							type="button"
							data-testid="editor-up"
							disabled={!selectedId}
							onclick={() => selectedId && store.moveNodeUp(selectedId)}
						>
							↑
						</button>
						<button
							type="button"
							data-testid="editor-down"
							disabled={!selectedId}
							onclick={() => selectedId && store.moveNodeDown(selectedId)}
						>
							↓
						</button>
					</div>
					{#if !hideChromeActions}
						<div class="group">
							<button type="button" data-testid="editor-save" disabled={saving} onclick={save}>
								{saving ? 'Saving…' : 'Save'}
							</button>
							<button type="button" data-testid="editor-reload" onclick={reload}>Reload</button>
							{#if previewHref}
								<a class="preview" data-testid="editor-preview" href={previewHref}>Preview</a>
							{/if}
						</div>
					{/if}
				</header>

				{#if status}
					<p class="status" data-testid="editor-status" role="status">{status}</p>
				{/if}

				{#if sections.length > 0}
					<nav class="section-tabs" data-testid="section-tabs" aria-label="Lesson sections">
						<button
							type="button"
							class:active={activeSectionId === 'all'}
							onclick={() => (activeSectionId = 'all')}
						>
							All
						</button>
						{#each sections as section}
							<button
								type="button"
								class:active={activeSectionId === section.id}
								title={section.title || section.id}
								onclick={() => (activeSectionId = section.id)}
							>
								{section.title || section.id}
							</button>
						{/each}
					</nav>
				{/if}

				<div class="canvas-wrap">
					<DocumentCanvas
						document={viewDocument ?? doc}
						selectedNodeId={selectedId}
						editable
						onSelectNode={(id) => store.selectNode(id)}
						onUpdateNodeText={(id, text) => store.updateNodeText(id, text)}
						onUpdateListItems={(id, items) => store.updateListItems(id, items)}
						onUpdateHeading={(id, patch) => store.updateHeading(id, patch)}
						onUpdateCallout={(id, patch) => store.updateCallout(id, patch)}
						onUpdateFigure={(id, patch) => store.updateFigure(id, patch)}
						onUpdateTable={(id, patch) => store.updateTable(id, patch)}
						onUpdateInteraction={(id, patch) => store.updateInteraction(id, patch)}
					/>
				</div>
			</div>
		</div>
	</div>
{/if}

<style>
	.document-editor {
		display: grid;
		gap: 14px;
	}
	.layout {
		display: grid;
		grid-template-columns: 180px minmax(0, 1fr);
		gap: 16px;
		align-items: start;
	}
	.palette {
		position: sticky;
		top: 1rem;
		display: grid;
		gap: 4px;
		padding: 12px;
		border: 1px solid var(--rule, #ccc);
		border-radius: 12px;
		background: var(--surface, #fff);
	}
	.palette-title {
		margin: 0.5rem 0 0.25rem;
		font-size: 0.7rem;
		font-weight: 650;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--ink-3, #888);
	}
	.palette-title:first-child {
		margin-top: 0;
	}
	.palette-item {
		text-align: left;
		border: none;
		background: transparent;
		padding: 0.45rem 0.55rem;
		border-radius: 8px;
		font: inherit;
		font-size: 0.8125rem;
		color: var(--ink-2, #555);
		cursor: pointer;
		text-transform: capitalize;
	}
	.palette-item:hover,
	.palette-item.active {
		background: var(--accent-soft, #e7f0ea);
		color: var(--accent, #1c5d45);
	}
	.palette-hint {
		margin: 0;
		font-size: 0.7rem;
		color: var(--ink-3, #888);
		line-height: 1.35;
	}
	.ix-list {
		margin: 0;
		padding-left: 1rem;
		font-size: 0.75rem;
		color: var(--ink-2, #555);
		text-transform: capitalize;
	}
	.main {
		display: grid;
		gap: 12px;
		min-width: 0;
	}
	.toolbar {
		display: flex;
		flex-wrap: wrap;
		gap: 12px;
		justify-content: space-between;
		align-items: center;
		padding: 10px 12px;
		border: 1px solid var(--rule, #ccc);
		border-radius: 12px;
		background: var(--surface, #f7f7f5);
	}
	.group {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		align-items: center;
	}
	button,
	.preview {
		border: 1px solid var(--rule, #ccc);
		border-radius: 8px;
		background: var(--paper, #fff);
		color: var(--ink, #1a1a1a);
		font: inherit;
		font-size: 13px;
		padding: 6px 10px;
		cursor: pointer;
		text-decoration: none;
	}
	.section-tabs {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.section-tabs button {
		max-width: 12rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.section-tabs button.active {
		font-weight: 600;
		border-color: var(--ink, #1a1a1a);
	}
	.canvas-wrap {
		border: 1px solid var(--rule, #ccc);
		border-radius: 12px;
		padding: 16px;
		background: var(--surface, #fff);
	}
	button:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}
	.status {
		margin: 0;
		font-size: 13px;
		color: var(--ink-2, #444);
	}
	@media (max-width: 800px) {
		.layout {
			grid-template-columns: 1fr;
		}
		.palette {
			position: static;
			grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
		}
	}
</style>
