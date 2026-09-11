<script lang="ts">
	/**
	 * LearnDocument v2 authoring surface: edit / add / delete / reorder / save / reload / preview.
	 * Uses the canonical LearnDocument — not a separate editor-only model.
	 */
	import { DOCUMENT_PRIMITIVE_KINDS, isLearnDocument, type LearnDocument } from './types';
	import type { AddableKind } from './document-state';
	import { createLearnDocumentStore } from './document-state.svelte';
	import DocumentCanvas from './DocumentCanvas.svelte';
	import {
		getBuilderLesson,
		updateBuilderLesson
	} from '$lib/learn/authoring/builder/api/lesson-crud';

	interface Props {
		document: LearnDocument;
		lessonId?: string | null;
		previewHref?: string | null;
		onDocumentChange?: (doc: LearnDocument) => void;
	}

	let {
		document: initialDocument,
		lessonId = null,
		previewHref = null,
		onDocumentChange = undefined
	}: Props = $props();

	const store = createLearnDocumentStore();
	store.loadDocument(initialDocument);

	let status = $state<string | null>(null);
	let saving = $state(false);
	let addKind = $state<AddableKind>('paragraph');

	$effect(() => {
		if (store.document) onDocumentChange?.(store.document);
	});

	const doc = $derived(store.document);
	const selectedId = $derived(store.selectedNodeId);

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
		<header class="toolbar">
			<div class="group">
				<label>
					<span class="sr">Add node</span>
					<select bind:value={addKind} aria-label="Add node kind">
						{#each DOCUMENT_PRIMITIVE_KINDS as kind}
							<option value={kind}>{kind}</option>
						{/each}
					</select>
				</label>
				<button type="button" data-testid="editor-add" onclick={addSelectedKind}>Add</button>
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
			<div class="group">
				<button type="button" data-testid="editor-save" disabled={saving} onclick={save}>
					{saving ? 'Saving…' : 'Save'}
				</button>
				<button type="button" data-testid="editor-reload" onclick={reload}>Reload</button>
				{#if previewHref}
					<a class="preview" data-testid="editor-preview" href={previewHref}>Preview</a>
				{/if}
			</div>
		</header>

		{#if status}
			<p class="status" data-testid="editor-status" role="status">{status}</p>
		{/if}

		<DocumentCanvas
			document={doc}
			selectedNodeId={selectedId}
			editable
			onSelectNode={(id) => store.selectNode(id)}
			onUpdateNodeText={(id, text) => store.updateNodeText(id, text)}
			onUpdateListItems={(id, items) => store.updateListItems(id, items)}
			onUpdateHeading={(id, patch) => store.updateHeading(id, patch)}
			onUpdateCallout={(id, patch) => store.updateCallout(id, patch)}
			onUpdateFigure={(id, patch) => store.updateFigure(id, patch)}
			onUpdateTable={(id, patch) => store.updateTable(id, patch)}
		/>
	</div>
{/if}

<style>
	.document-editor {
		display: grid;
		gap: 14px;
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
	select,
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
	button:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}
	.status {
		margin: 0;
		font-size: 13px;
		color: var(--ink-2, #444);
	}
	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
	}
</style>
