<script lang="ts">
	import { onMount } from 'svelte';
	import {
		approveConceptCards,
		getConceptCards,
		reuseConceptCard,
		searchConceptCards,
		updateConceptCard,
		type CardLibraryItem,
		type ConceptCard
	} from '$lib/builder/api/concept-cards';

	let {
		packId,
		title,
		onApproved
	}: {
		packId: string;
		title: string;
		onApproved: () => void | Promise<void>;
	} = $props();

	let cards = $state<ConceptCard[]>([]);
	let index = $state(0);
	let loading = $state(true);
	let saving = $state(false);
	let approving = $state(false);
	let error = $state<string | null>(null);
	let saveLabel = $state('All changes saved');
	let activeSave: Promise<boolean> | null = null;
	let libraryOpen = $state(false);
	let librarySearch = $state('');
	let libraryCards = $state<CardLibraryItem[]>([]);
	let libraryLoading = $state(false);
	let reuseBusy = $state<string | null>(null);

	const card = $derived(cards[index] ?? null);

	onMount(() => {
		void getConceptCards(packId)
			.then((rows) => {
				cards = rows;
			})
			.catch((cause) => {
				error = cause instanceof Error ? cause.message : 'Could not load concept cards.';
			})
			.finally(() => {
				loading = false;
			});
	});

	function replaceCurrent(next: ConceptCard): void {
		cards = cards.map((item, itemIndex) => (itemIndex === index ? next : item));
	}

	async function persistCurrent(): Promise<boolean> {
		if (!card) return false;
		saving = true;
		error = null;
		saveLabel = 'Saving…';
		try {
			const saved = await updateConceptCard(packId, card);
			replaceCurrent(saved);
			saveLabel = 'All changes saved';
			return true;
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'Could not save this concept card.';
			saveLabel = 'Save failed';
			return false;
		} finally {
			saving = false;
		}
	}

	function saveCurrent(): Promise<boolean> {
		if (activeSave) return activeSave;
		activeSave = persistCurrent().finally(() => {
			activeSave = null;
		});
		return activeSave;
	}

	async function move(nextIndex: number): Promise<void> {
		if (!(await saveCurrent())) return;
		index = Math.max(0, Math.min(nextIndex, cards.length - 1));
	}

	function addMisconception(): void {
		if (!card) return;
		const used = new Set(card.misconceptions.map((item) => item.id));
		let number = card.misconceptions.length + 1;
		while (used.has(`M${number}`)) number += 1;
		card.misconceptions = [
			...card.misconceptions,
			{ id: `M${number}`, description: '', source: 'teacher' }
		];
		saveLabel = 'Unsaved changes';
	}

	function removeMisconception(itemIndex: number): void {
		if (!card) return;
		card.misconceptions = card.misconceptions.filter((_, current) => current !== itemIndex);
		saveLabel = 'Unsaved changes';
	}

	async function searchLibrary(): Promise<void> {
		libraryLoading = true;
		error = null;
		try {
			libraryCards = await searchConceptCards(librarySearch);
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'Could not search your card library.';
		} finally {
			libraryLoading = false;
		}
	}

	async function openLibrary(): Promise<void> {
		libraryOpen = true;
		await searchLibrary();
	}

	async function reuse(source: CardLibraryItem): Promise<void> {
		if (!card || reuseBusy) return;
		reuseBusy = source.card_id;
		error = null;
		try {
			const reused = await reuseConceptCard(packId, source.card_id, card.id);
			replaceCurrent(reused);
			saveLabel = `Reused from ${source.title}`;
			libraryOpen = false;
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'Could not reuse this card.';
		} finally {
			reuseBusy = null;
		}
	}

	async function approve(): Promise<void> {
		if (!(await saveCurrent())) return;
		approving = true;
		error = null;
		try {
			await approveConceptCards(packId);
			await onApproved();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'Could not approve concept cards.';
		} finally {
			approving = false;
		}
	}
</script>

<main class="min-h-screen bg-slate-100 px-4 py-8" data-testid="concept-card-review">
	<section class="mx-auto max-w-3xl">
		<header class="mb-6 flex flex-wrap items-end justify-between gap-3">
			<div>
				<p class="text-xs font-semibold uppercase tracking-[0.18em] text-blue-700">Review concepts</p>
				<h1 class="mt-1 text-2xl font-bold text-slate-950">{title}</h1>
			</div>
			{#if cards.length > 0}
				<p class="text-sm font-medium text-slate-600">Card {index + 1} of {cards.length}</p>
			{/if}
		</header>

		{#if loading}
			<div class="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">Loading concept cards…</div>
		{:else if error && cards.length === 0}
			<div class="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-800" role="alert">{error}</div>
		{:else if !card}
			<div class="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-900">No concept cards were found for this lesson.</div>
		{:else}
			<div class="mb-5 flex justify-center gap-2" aria-label="Concept card progress">
				{#each cards as _, dotIndex}
					<button
						type="button"
						class={`h-2.5 w-2.5 rounded-full ${dotIndex === index ? 'bg-blue-700' : 'bg-slate-300'}`}
						aria-label={`Open card ${dotIndex + 1}`}
						onclick={() => void move(dotIndex)}
					></button>
				{/each}
			</div>

			<article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
				<label class="block text-sm font-semibold text-slate-800" for="card-title">Concept title</label>
				<input
					id="card-title"
					class="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-lg font-semibold text-slate-950"
					bind:value={card.title}
					oninput={() => (saveLabel = 'Unsaved changes')}
					onblur={() => void saveCurrent()}
				/>
				<div class="mt-1 flex flex-wrap items-center justify-between gap-2">
					<p class="text-xs text-slate-500">{card.id}{card.source_card_id ? ' · reused from your library' : ''}</p>
					<button type="button" class="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700" onclick={() => void openLibrary()}>Reuse from library</button>
				</div>

				<label class="mt-6 block text-sm font-semibold text-slate-800" for="card-objective">By the end, learners can</label>
				<textarea
					id="card-objective"
					class="mt-2 min-h-24 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900"
					bind:value={card.objective}
					oninput={() => (saveLabel = 'Unsaved changes')}
					onblur={() => void saveCurrent()}
				></textarea>

				<div class="mt-6 flex items-center justify-between gap-3">
					<h2 class="text-sm font-semibold text-slate-800">Mistakes they’ll make</h2>
					<span class="text-xs text-slate-500">{card.teacher_edited ? 'edited by you' : 'drafted'}</span>
				</div>

				{#if card.misconceptions.length === 0}
					<div class="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
						{card.no_known_misconceptions
							? 'No common misconception is known for this concept. You may still add one.'
							: 'No misconceptions — the quiz for this card won’t diagnose anything.'}
					</div>
				{:else}
					<div class="mt-3 divide-y divide-slate-200 rounded-xl border border-slate-200">
						{#each card.misconceptions as misconception, misconceptionIndex (misconception.id)}
							<div class="grid grid-cols-[auto_1fr_auto] items-start gap-3 p-3">
								<span class="pt-2 text-xs font-bold text-slate-500">{misconception.id}</span>
								<div>
									<textarea
										aria-label={`Misconception ${misconception.id}`}
										class="min-h-16 w-full resize-y rounded-md border border-slate-300 px-2 py-1.5 text-sm"
										bind:value={misconception.description}
										oninput={() => (saveLabel = 'Unsaved changes')}
										onblur={() => void saveCurrent()}
									></textarea>
									<span class="text-xs text-slate-500">{misconception.source === 'teacher' ? 'yours' : 'drafted'}</span>
								</div>
								<button
									type="button"
									class="rounded-md px-2 py-1 text-sm font-semibold text-red-700 hover:bg-red-50"
									aria-label={`Remove misconception ${misconception.id}`}
									onclick={() => removeMisconception(misconceptionIndex)}
								>Remove</button>
							</div>
						{/each}
					</div>
				{/if}

				<button
					type="button"
					class="mt-3 rounded-lg border border-blue-200 px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50"
					onclick={addMisconception}
				>+ Add one you’ve seen</button>

				<div class="mt-6 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-950">
					These drive the quiz. A wrong answer will be written for each one, so a student’s choice shows which belief they hold.
				</div>
			</article>

			{#if error}
				<p class="mt-4 text-sm text-red-700" role="alert">{error}</p>
			{/if}
			<footer class="mt-5 flex flex-wrap items-center justify-between gap-3">
				<p class="text-xs text-slate-500" aria-live="polite">{saveLabel}</p>
				<div class="flex gap-2">
					{#if cards.length > 1}
						<button
							type="button"
							class="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold disabled:opacity-50"
							disabled={index === 0 || saving || approving}
							onclick={() => void move(index - 1)}
						>← Previous</button>
					{/if}
					{#if index < cards.length - 1}
						<button
							type="button"
							class="rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
							disabled={saving}
							onclick={() => void move(index + 1)}
						>Next →</button>
					{:else}
						<button
							type="button"
							class="rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
							disabled={saving || approving}
							onclick={() => void approve()}
						>{approving ? 'Starting generation…' : 'Approve and generate'}</button>
					{/if}
				</div>
			</footer>
		{/if}
	</section>
</main>

{#if libraryOpen}
	<div class="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4" role="presentation">
		<div class="max-h-[85vh] w-full max-w-2xl overflow-auto rounded-2xl bg-white p-5 shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="card-library-title">
			<div class="flex items-start justify-between gap-3">
				<div><p class="text-xs font-semibold uppercase tracking-[0.18em] text-blue-700">Your library</p><h2 id="card-library-title" class="mt-1 text-xl font-bold">Reuse a concept card</h2></div>
				<button type="button" class="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold" onclick={() => (libraryOpen = false)}>Close</button>
			</div>
			<form class="mt-4 flex gap-2" onsubmit={(event) => { event.preventDefault(); void searchLibrary(); }}>
				<input class="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm" bind:value={librarySearch} aria-label="Search concept cards" placeholder="Search title, objective, or slug" />
				<button type="submit" class="rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white">Search</button>
			</form>
			{#if libraryLoading}
				<p class="mt-4 text-sm text-slate-600">Searching…</p>
			{:else if libraryCards.length === 0}
				<p class="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">No matching cards yet.</p>
			{:else}
				<div class="mt-4 grid gap-3">
					{#each libraryCards as libraryCard}
						<article class="rounded-xl border border-slate-200 p-4">
							<div class="flex items-start justify-between gap-3">
								<div><h3 class="font-semibold text-slate-950">{libraryCard.title}</h3><p class="mt-1 text-xs text-slate-500">{libraryCard.slug}</p></div>
								<button type="button" disabled={reuseBusy !== null || libraryCard.card_id === card?.source_card_id} class="rounded-lg bg-blue-700 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50" onclick={() => void reuse(libraryCard)}>{reuseBusy === libraryCard.card_id ? 'Reusing…' : 'Use this card'}</button>
							</div>
							<p class="mt-3 text-sm text-slate-700">{libraryCard.objective}</p>
							<p class="mt-2 text-xs text-slate-500">{libraryCard.misconceptions.length} misconception {libraryCard.misconceptions.length === 1 ? 'belief' : 'beliefs'}</p>
						</article>
					{/each}
				</div>
			{/if}
		</div>
	</div>
{/if}
