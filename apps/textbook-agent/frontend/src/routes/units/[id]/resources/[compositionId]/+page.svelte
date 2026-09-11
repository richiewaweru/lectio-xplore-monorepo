<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { getUnitResource } from '$lib/api/units';
	import LectioPageDocumentView from '$lib/print/components/studio/LectioPageDocumentView.svelte';
	import { extractLectioDocumentV2 } from '$lib/print/studio/document-version';
	import type { ResourceComposition } from '$lib/types/units';
	import type { LectioDocument } from '@lectio/page/contract';
	import '$lib/print/styles/print.css';

	const unitId = $derived(page.params.id ?? '');
	const compositionId = $derived(page.params.compositionId ?? '');
	const printMode = $derived(page.url.searchParams.get('print') === 'true');

	let composition = $state<ResourceComposition | null>(null);
	let document = $state<LectioDocument | null>(null);
	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			composition = await getUnitResource(unitId, compositionId);
			const extracted = extractLectioDocumentV2(composition.document);
			if (!extracted) {
				error =
					'This resource has no LectioDocument v2 payload. Legacy SectionContent packs are not rendered.';
				return;
			}
			document = extracted;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not render this resource.';
		}
	});

	function exportJson(): void {
		if (!composition) return;
		const blob = new Blob([JSON.stringify(composition.document, null, 2)], { type: 'application/json' });
		const url = URL.createObjectURL(blob);
		const anchor = window.document.createElement('a');
		anchor.href = url;
		anchor.download = `${composition.projection}-${composition.id}.json`;
		anchor.click();
		URL.revokeObjectURL(url);
	}
</script>

<svelte:head><title>{composition ? composition.projection.replaceAll('_', ' ') : 'Resource'} · Xplore</title></svelte:head>

<main data-renderer="lectio-page-v2" data-print-route="unit-resource" data-generation-complete={document || error ? 'true' : 'false'}>
	{#if !printMode}
		<header class="resource-toolbar">
			<a href={`/units/${unitId}`}>← Unit workspace</a>
			{#if composition}<strong>{composition.projection.replaceAll('_', ' ')}</strong>{/if}
			<div><button type="button" onclick={() => window.print()}>Print</button><button type="button" onclick={exportJson}>Export JSON</button></div>
		</header>
	{/if}
	{#if error}
		<p class="resource-error" role="alert">{error}</p>
	{:else if document}
		<LectioPageDocumentView {document} edition="teacher" />
	{:else}
		<p class="loading">Preparing resource…</p>
	{/if}
</main>

<style>
	.resource-toolbar { position: sticky; z-index: 10; top: 0; display: flex; align-items: center; justify-content: space-between; gap: 16px; border-bottom: 1px solid var(--rule); background: var(--surface); padding: 10px 18px; font-size: 12px; }
	.resource-toolbar > div { display: flex; gap: 7px; }
	.resource-toolbar a { color: var(--accent); text-decoration: none; }
	.resource-toolbar button { border: 1px solid var(--rule); border-radius: 6px; background: var(--surface); padding: 7px 10px; cursor: pointer; }
	.resource-error, .loading { max-width: 760px; margin: 40px auto; padding: 18px; }
	.resource-error { color: #873f30; }
	@media print { .resource-toolbar { display: none; } }
</style>
