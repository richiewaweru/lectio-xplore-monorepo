<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { providePrintMode } from 'lectio';
	import { fetchV3Document, getXplorePack } from '$lib/api/v3';
	import V3LectioPrintDocumentView from '$lib/components/studio/V3LectioPrintDocumentView.svelte';
	import {
		adaptV3PackToLectioDocument,
		type V3PackDocument
	} from '$lib/studio/v3-pack-to-lectio-document';
	import type { GenerationDocument } from '$lib/types';
	import '$lib/styles/print.css';

	providePrintMode(() => true);

	let documents = $state<Array<{ label: string; document: GenerationDocument }>>([]);
	let keyDocument = $state<GenerationDocument | null>(null);
	let ready = $state(false);
	let error = $state<string | null>(null);
	const packId = $derived(page.params.pack_id ?? '');

	onMount(async () => {
		try {
			const pack = await getXplorePack(packId);
			if (!pack.editor_ready) throw new Error('Wait for all variants to land or fail before printing.');
			const requested = new Set(
				(page.url.searchParams.get('variants') ?? '')
					.split(',')
					.map((label) => label.trim())
					.filter(Boolean)
			);
			const keyOnly = page.url.searchParams.get('keyOnly') === 'true';
			const selected = pack.variants.filter(
				(variant) =>
					variant.status === 'landed' &&
					variant.generation_id &&
					(requested.size === 0 || requested.has(variant.label))
			);
			if (!keyOnly && selected.length === 0) throw new Error('Choose at least one landed variant.');
			const loaded = await Promise.all(
				selected.map(async (variant) => ({
					variant,
					pack: (await fetchV3Document(variant.generation_id as string)) as V3PackDocument
				}))
			);
			if (!keyOnly) {
				documents = loaded.map(({ variant, pack: documentPack }) => ({
					label: variant.label,
					document: adaptV3PackToLectioDocument(documentPack, {
						routeGenerationId: variant.generation_id ?? undefined,
						includeAnswerKey: false
					})
				}));
			}
			const keySource =
				loaded[0]?.pack ??
				((await fetchV3Document(
					pack.variants.find((variant) => variant.status === 'landed')?.generation_id ?? ''
				)) as V3PackDocument);
			keyDocument = adaptV3PackToLectioDocument(
				{ ...keySource, sections: [] },
				{ includeAnswerKey: true }
			);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not prepare this pack for print.';
		} finally {
			ready = true;
		}
	});
</script>

<svelte:head><title>Print Xplore pack</title></svelte:head>

<main data-generation-complete={ready ? 'true' : 'false'} data-renderer="lectio" data-print-route="xplore-pack">
	{#if error}
		<p class="mx-auto max-w-xl p-8 text-red-900">{error}</p>
	{:else if ready}
		{#each documents as item}
			<section class="pack-print-document" aria-label={`${item.label} booklet`}>
				<div class="variant-print-label">{item.label}</div>
				<V3LectioPrintDocumentView document={item.document} />
			</section>
		{/each}
		{#if keyDocument}
			<section class="pack-print-document diagnostic-key" aria-label="Shared diagnostic answer key">
				<V3LectioPrintDocumentView document={keyDocument} />
			</section>
		{/if}
	{:else}
		<p class="p-8">Preparing pack…</p>
	{/if}
</main>

<style>
	.pack-print-document {
		break-after: page;
	}

	.pack-print-document:last-child {
		break-after: auto;
	}

	.variant-print-label {
		margin: 0 auto 1rem;
		max-width: 72rem;
		font-weight: 700;
	}

	@media print {
		.variant-print-label {
			padding: 0 12mm;
		}
	}
</style>
