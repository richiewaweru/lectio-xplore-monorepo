<script lang="ts">
	import type { LessonDocument } from 'lectio';
	import type { DocumentStore } from '$lib/builder/stores/document.svelte';
	import {
		listVersions,
		restoreVersionWithBackup,
		saveVersionSnapshot,
		type DocumentVersion
	} from '$lib/builder/persistence/idb-store';
	import { downloadLessonDocument } from '$lib/builder/utils/file-io';
	import LessonReadOnlyView from '$lib/builder/components/canvas/LessonReadOnlyView.svelte';
	import { History, X } from 'lucide-svelte';

	let {
		open = $bindable(false),
		document: doc,
		store
	}: {
		open?: boolean;
		document: LessonDocument;
		store: DocumentStore;
	} = $props();

	let versions = $state<DocumentVersion[]>([]);
	let selectedId = $state<string | null>(null);
	let saveLabel = $state('');
	let loading = $state(false);
	let error = $state<string | null>(null);

	const selected = $derived(versions.find((v) => v.id === selectedId) ?? null);

	async function refresh(): Promise<void> {
		versions = await listVersions(doc.id);
		if (versions.length > 0 && !selectedId) {
			selectedId = versions[0]!.id;
		}
		if (selectedId && !versions.some((v) => v.id === selectedId)) {
			selectedId = versions[0]?.id ?? null;
		}
	}

	$effect(() => {
		if (!open) return;
		void refresh();
	});

	async function manualSave(): Promise<void> {
		error = null;
		loading = true;
		try {
			await saveVersionSnapshot(doc.id, doc, saveLabel.trim() || undefined);
			saveLabel = '';
			await refresh();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Could not save version';
		} finally {
			loading = false;
		}
	}

	async function restore(): Promise<void> {
		if (!selected || !store.document) return;
		if (!confirm('Replace the current lesson with this version? Your current state will be saved as a version first.')) {
			return;
		}
		error = null;
		loading = true;
		try {
			const next = await restoreVersionWithBackup(store.document, selected);
			store.loadDocument(next);
			await store.flushSave();
			open = false;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Restore failed';
		} finally {
			loading = false;
		}
	}

	function downloadSelected(): void {
		if (!selected) return;
		downloadLessonDocument(selected.snapshot);
	}
</script>

{#if open}
	<div
		class="version-panel-overlay fixed inset-0 z-50 flex items-stretch justify-end bg-black/40 p-0 sm:p-4"
		role="presentation"
		onclick={(e) => e.target === e.currentTarget && (open = false)}
	>
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<div
			class="flex h-full w-full max-w-3xl flex-col bg-white shadow-xl sm:max-h-[min(90vh,48rem)] sm:rounded-xl"
			role="dialog"
			aria-labelledby="version-panel-title"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
		>
			<div class="flex items-center justify-between border-b border-slate-200 px-4 py-3">
				<h2 id="version-panel-title" class="flex items-center gap-2 text-lg font-semibold text-slate-900">
					<History size={20} aria-hidden="true" />
					Version history
				</h2>
				<button
					type="button"
					class="rounded-md p-2 text-slate-600 hover:bg-slate-100"
					aria-label="Close"
					onclick={() => (open = false)}
				>
					<X size={20} />
				</button>
			</div>

			<div class="flex flex-1 flex-col gap-3 overflow-hidden p-4 sm:flex-row">
				<div class="flex max-h-48 flex-col border-b border-slate-100 sm:max-h-none sm:w-56 sm:border-b-0 sm:border-r sm:pr-3">
					<div class="mb-2 flex gap-2">
						<input
							bind:value={saveLabel}
							type="text"
							placeholder="Label (optional)"
							class="min-w-0 flex-1 rounded border border-slate-200 px-2 py-1 text-sm"
						/>
						<button
							type="button"
							class="shrink-0 rounded bg-slate-800 px-2 py-1 text-xs font-medium text-white hover:bg-slate-900 disabled:opacity-50"
							disabled={loading}
							data-testid="version-save-manual"
							onclick={() => void manualSave()}
						>
							Save
						</button>
					</div>
					<p class="mb-1 text-xs font-medium text-slate-500">Snapshots</p>
					<ul class="min-h-0 flex-1 space-y-1 overflow-y-auto text-sm">
						{#each versions as v (v.id)}
							<li>
								<button
									type="button"
									class="w-full rounded px-2 py-1.5 text-left hover:bg-slate-100 {selectedId === v.id
										? 'bg-blue-50 font-medium text-blue-900'
										: 'text-slate-800'}"
									onclick={() => (selectedId = v.id)}
								>
									<span class="block truncate">{v.label || 'Version'}</span>
									<span class="block text-xs text-slate-500">{v.created_at.slice(0, 19).replace('T', ' ')}</span>
								</button>
							</li>
						{/each}
					</ul>
					{#if versions.length === 0}
						<p class="text-xs text-slate-500">No versions yet.</p>
					{/if}
				</div>

				<div class="flex min-h-0 min-w-0 flex-1 flex-col">
					{#if error}
						<p class="mb-2 text-sm text-red-600">{error}</p>
					{/if}
					<div class="mb-2 flex flex-wrap gap-2">
						<button
							type="button"
							class="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
							disabled={!selected || loading}
							data-testid="version-restore"
							onclick={() => void restore()}
						>
							Restore
						</button>
						<button
							type="button"
							class="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
							disabled={!selected}
							data-testid="version-download"
							onclick={downloadSelected}
						>
							Download JSON
						</button>
					</div>
					<div class="min-h-0 flex-1 overflow-y-auto rounded border border-slate-100 bg-slate-50 p-3">
						{#if selected}
							<LessonReadOnlyView document={selected.snapshot} />
						{:else}
							<p class="text-sm text-slate-500">Select a version to preview.</p>
						{/if}
					</div>
				</div>
			</div>
		</div>
	</div>
{/if}
