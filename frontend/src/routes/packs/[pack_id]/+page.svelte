<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { page } from '$app/state';
	import {
		deleteXploreVariant,
		getXplorePack,
		retryXploreVariant
	} from '$lib/api/v3';
	import type { V3XplorePack } from '$lib/types/v3';

	let pack = $state<V3XplorePack | null>(null);
	let error = $state<string | null>(null);
	let busyLabel = $state<string | null>(null);
	let printSelection = $state<string[]>([]);
	let timer: ReturnType<typeof setInterval> | null = null;
	const packId = $derived(page.params.pack_id ?? '');
	const landed = $derived(pack?.variants.filter((variant) => variant.status === 'landed') ?? []);
	const completedCount = $derived(
		pack?.variants.filter((variant) => ['landed', 'failed'].includes(variant.status)).length ?? 0
	);

	async function refresh(): Promise<void> {
		try {
			pack = await getXplorePack(packId);
			error = null;
			printSelection = printSelection.filter((label) =>
				pack?.variants.some((variant) => variant.label === label && variant.status === 'landed')
			);
			if (pack.editor_ready && timer) {
				clearInterval(timer);
				timer = null;
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load pack.';
		}
	}

	async function retry(label: string): Promise<void> {
		busyLabel = label;
		error = null;
		try {
			pack = await retryXploreVariant(packId, label);
			if (!timer) timer = setInterval(() => void refresh(), 3000);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not retry this booklet.';
		} finally {
			busyLabel = null;
		}
	}

	async function remove(label: string): Promise<void> {
		if (!confirm(`Remove the ${label} booklet from this pack?`)) return;
		busyLabel = label;
		error = null;
		try {
			pack = await deleteXploreVariant(packId, label);
			printSelection = printSelection.filter((item) => item !== label);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not remove this booklet.';
		} finally {
			busyLabel = null;
		}
	}

	function togglePrint(label: string): void {
		printSelection = printSelection.includes(label)
			? printSelection.filter((item) => item !== label)
			: [...printSelection, label];
	}

	function openPrintSelection(): void {
		if (!pack?.editor_ready) return;
		for (const variant of landed) {
			if (printSelection.includes(variant.label) && variant.generation_id) {
				window.open(`/studio/generations/${encodeURIComponent(variant.generation_id)}`, '_blank');
			}
		}
	}

	onMount(() => {
		void refresh();
		timer = setInterval(() => void refresh(), 3000);
	});

	onDestroy(() => {
		if (timer) clearInterval(timer);
	});
</script>

<svelte:head><title>{pack ? `${pack.topic} · Xplore pack` : 'Xplore pack'}</title></svelte:head>

<section class="mx-auto grid max-w-6xl gap-6 px-4 py-8">
	{#if error}
		<p class="rounded-2xl border border-red-300 bg-red-50 px-4 py-3 text-sm font-medium text-red-900">{error}</p>
	{/if}

	{#if pack}
		<header class="rounded-3xl border border-border/60 bg-card p-6 shadow-sm">
			<div class="flex flex-wrap items-start justify-between gap-4">
				<div class="space-y-2">
					<p class="text-sm font-semibold uppercase tracking-[0.22em] text-muted-foreground">Xplore learning pack</p>
					<h1 class="text-3xl font-semibold tracking-tight">{pack.topic}</h1>
					<p class="text-muted-foreground">{pack.subject} · {completedCount} of {pack.variants.length} variants landed or failed</p>
				</div>
				<span class={`rounded-full px-3 py-1 text-sm font-semibold ${pack.editor_ready ? 'bg-emerald-100 text-emerald-900' : 'bg-amber-100 text-amber-950'}`}>{pack.editor_ready ? 'Pack ready' : 'Generating in parallel'}</span>
			</div>
			<div class="mt-5 h-2 overflow-hidden rounded-full bg-muted" aria-label="Pack progress">
				<div class="h-full rounded-full bg-primary transition-all" style={`width: ${(completedCount / Math.max(pack.variants.length, 1)) * 100}%`}></div>
			</div>
			{#if !pack.editor_ready}
				<p class="mt-3 text-sm text-muted-foreground">The editor unlocks when every booklet has either landed or failed. A failed booklet does not block the others.</p>
			{/if}
		</header>

		<div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
			{#each pack.variants as variant}
				<article class="grid content-start gap-4 rounded-3xl border border-border/60 bg-card p-5 shadow-sm">
					<div class="flex items-start justify-between gap-3">
						<div>
							<h2 class="text-xl font-semibold">{variant.label}</h2>
							<p class="mt-1 text-sm leading-5 text-muted-foreground">{variant.group_description}</p>
						</div>
						<span class={`rounded-full px-2.5 py-1 text-xs font-bold uppercase tracking-wide ${variant.status === 'landed' ? 'bg-emerald-100 text-emerald-900' : variant.status === 'failed' ? 'bg-red-100 text-red-900' : 'bg-blue-100 text-blue-900'}`}>{variant.status}</span>
					</div>

					{#if variant.issues.length > 0}
						<div class="rounded-2xl border border-red-300 bg-red-50 p-3">
							<p class="text-sm font-semibold text-red-950">Issues for {variant.label}</p>
							<ul class="mt-2 list-disc space-y-1 pl-5 text-sm text-red-900">{#each variant.issues as issue}<li>{issue}</li>{/each}</ul>
						</div>
					{/if}

					<div class="flex flex-wrap gap-2">
						{#if pack.editor_ready && variant.status === 'landed' && variant.generation_id}
							<a class="rounded-xl bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground" href={`/studio/generations/${encodeURIComponent(variant.generation_id)}`}>Open editor</a>
						{:else if variant.can_retry}
							<button type="button" disabled={busyLabel === variant.label} class="rounded-xl bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50" onclick={() => retry(variant.label)}>{busyLabel === variant.label ? 'Retrying…' : 'Retry this variant'}</button>
						{/if}
						{#if pack.variants.length > 1}
							<button type="button" disabled={busyLabel === variant.label} class="rounded-xl border border-input px-3 py-2 text-sm font-semibold disabled:opacity-50" onclick={() => remove(variant.label)}>Remove</button>
						{/if}
					</div>
				</article>
			{/each}
		</div>

		<section class="grid gap-4 rounded-3xl border border-border/60 bg-card p-5 shadow-sm md:grid-cols-[1fr_auto] md:items-center">
			<div>
				<p class="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">Shared diagnostic</p>
				<h2 class="mt-1 text-xl font-semibold">{pack.shared_item_count} questions across all variants</h2>
				<p class="mt-1 text-sm text-muted-foreground">One item set, linked to the same approved misconceptions regardless of booklet wording.</p>
			</div>
			<a class="rounded-xl border border-input bg-background px-4 py-2 text-sm font-semibold" href={`/packs/${encodeURIComponent(packId)}/items`}>Review shared quiz</a>
		</section>

		<section class="space-y-4 rounded-3xl border border-border/60 bg-card p-5 shadow-sm">
			<div>
				<p class="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">Print picker</p>
				<h2 class="mt-1 text-xl font-semibold">Choose booklet versions</h2>
			</div>
			{#if pack.editor_ready && landed.length > 0}
				<div class="flex flex-wrap gap-3">
					{#each landed as variant}
						<label class="flex items-center gap-2 rounded-xl border border-input px-3 py-2 text-sm font-medium"><input type="checkbox" checked={printSelection.includes(variant.label)} onchange={() => togglePrint(variant.label)} />{variant.label}</label>
					{/each}
				</div>
				<button type="button" disabled={printSelection.length === 0} class="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50" onclick={openPrintSelection}>Open selected print views</button>
			{:else}
				<p class="text-sm text-muted-foreground">Print selection unlocks with the editors after all variants finish.</p>
			{/if}
		</section>
	{:else if !error}
		<p class="rounded-2xl border border-border/60 bg-card p-5 text-muted-foreground">Loading Xplore pack…</p>
	{/if}
</section>
