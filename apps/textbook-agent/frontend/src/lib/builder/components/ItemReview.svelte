<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getPackItems,
		regenerateCardItems,
		updatePackItem,
		type CardItemReview,
		type PackItem
	} from '$lib/builder/api/pack-items';

	let { packId }: { packId: string } = $props();

	let cards = $state<CardItemReview[]>([]);
	let cardIndex = $state(0);
	let editingId = $state<string | null>(null);
	let loading = $state(true);
	let saving = $state(false);
	let regenerating = $state(false);
	let error = $state<string | null>(null);

	const card = $derived(cards[cardIndex] ?? null);

	onMount(() => {
		void getPackItems(packId)
			.then((rows) => {
				cards = rows;
			})
			.catch((cause) => {
				error = cause instanceof Error ? cause.message : 'Could not load the shared quiz.';
			})
			.finally(() => {
				loading = false;
			});
	});

	function replaceCard(next: CardItemReview): void {
		cards = cards.map((row, index) => (index === cardIndex ? next : row));
	}

	function updateItem(itemId: string, change: (item: PackItem) => PackItem): void {
		if (!card) return;
		card.items = card.items.map((item) => (item.id === itemId ? change(item) : item));
	}

	async function saveItem(item: PackItem): Promise<void> {
		saving = true;
		error = null;
		try {
			replaceCard(await updatePackItem(packId, item));
			editingId = null;
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'Could not save this quiz item.';
		} finally {
			saving = false;
		}
	}

	async function regenerate(): Promise<void> {
		if (!card) return;
		regenerating = true;
		error = null;
		try {
			replaceCard(await regenerateCardItems(packId, card.card_id));
			editingId = null;
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'Could not regenerate this card’s quiz.';
		} finally {
			regenerating = false;
		}
	}

	function misconceptionLabel(id: string | null): string {
		if (!id || !card) return '⚠ untagged';
		const row = card.misconceptions.find((item) => item.id === id);
		return row ? `${id} · ${row.description}` : `${id} · unknown`;
	}
</script>

<main class="min-h-screen bg-slate-100 px-4 py-8" data-testid="item-review">
	<section class="mx-auto max-w-4xl">
		<header class="mb-6">
			<p class="text-xs font-semibold uppercase tracking-[0.18em] text-blue-700">Shared quiz</p>
			<h1 class="mt-1 text-2xl font-bold text-slate-950">Review diagnostic items</h1>
			<p class="mt-2 text-sm text-slate-600">The same quiz is used by every booklet in this pack.</p>
		</header>

		{#if loading}
			<div class="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">Loading quiz items…</div>
		{:else if error && cards.length === 0}
			<div class="rounded-2xl border border-red-200 bg-red-50 p-5 text-sm text-red-800" role="alert">{error}</div>
		{:else if cards.length === 0}
			<div class="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">No concept cards are available for this pack.</div>
		{:else}
			<nav class="mb-4 flex flex-wrap gap-2" aria-label="Quiz cards">
				{#each cards as row, index}
					<button
						type="button"
						class={`rounded-full px-3 py-1.5 text-sm font-semibold ${index === cardIndex ? 'bg-blue-700 text-white' : 'border border-slate-300 bg-white text-slate-700'}`}
						onclick={() => {
							cardIndex = index;
							editingId = null;
						}}
					>{row.card_title}</button>
				{/each}
			</nav>

			{#if card}
				<section class={`rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7 ${regenerating ? 'opacity-60' : ''}`}>
					<div class="flex flex-wrap items-start justify-between gap-3">
						<div>
							<h2 class="text-xl font-bold text-slate-950">Quiz · {card.card_title}</h2>
							<p class="mt-1 text-xs text-slate-500">{card.items.length} questions · {card.unmapped_options} untagged options</p>
						</div>
						<span class="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-800">shared by all booklets</span>
					</div>

					{#if card.stale}
						<div class="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
							This quiz is stale because its concept card changed. Your edits are kept.
						</div>
					{/if}
					{#each card.missing_misconceptions as missing}
						<div class="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
							{missing} isn’t tested by any question.
						</div>
					{/each}

					<div class="mt-5 divide-y divide-slate-200">
						{#each card.items as item, itemIndex (item.id)}
							<article class="py-5">
								<div class="flex items-start gap-3">
									<span class="pt-1 text-sm font-bold text-slate-500">Q{itemIndex + 1}</span>
									<div class="min-w-0 flex-1">
										{#if editingId === item.id}
											<textarea
												aria-label={`Question ${itemIndex + 1}`}
												class="min-h-20 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold"
												value={item.prompt_text}
												oninput={(event) =>
													updateItem(item.id, (current) => ({
														...current,
														prompt_text: event.currentTarget.value
													}))}
											></textarea>
										{:else}
											<p class="font-semibold text-slate-950">{item.prompt_text}</p>
										{/if}

										<div class="mt-3 space-y-2">
											{#each item.options as option, optionIndex (option.key)}
												<div class="grid grid-cols-[auto_1fr] gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm">
													<span aria-hidden="true">{option.correct ? '●' : '○'}</span>
													<div class="flex flex-wrap items-center justify-between gap-2">
														{#if editingId === item.id}
															<input
																aria-label={`Option ${option.key}`}
																class="min-w-48 flex-1 rounded border border-slate-300 px-2 py-1"
																value={option.text}
																oninput={(event) =>
																	updateItem(item.id, (current) => ({
																		...current,
																		options: current.options.map((row, index) =>
																			index === optionIndex
																				? { ...row, text: event.currentTarget.value }
																				: row
																		)
																	}))}
															/>
															{#if !option.correct}
																<select
																	aria-label={`Diagnosis for option ${option.key}`}
																	class="rounded border border-slate-300 px-2 py-1"
																	value={option.diagnoses ?? ''}
																	onchange={(event) =>
																		updateItem(item.id, (current) => ({
																			...current,
																			options: current.options.map((row, index) =>
																				index === optionIndex
																					? { ...row, diagnoses: event.currentTarget.value || null }
																					: row
																			)
																		}))}
																>
																	<option value="">Untagged</option>
																	{#each card.misconceptions as misconception}
																		<option value={misconception.id}>{misconception.id}</option>
																	{/each}
																</select>
															{:else}
																<span class="font-semibold text-emerald-700">correct</span>
															{/if}
														{:else}
															<span>{option.key}. {option.text}</span>
															<span class={option.correct ? 'font-semibold text-emerald-700' : option.diagnoses ? 'text-slate-600' : 'font-semibold text-amber-700'}>
																{option.correct ? 'correct' : misconceptionLabel(option.diagnoses)}
															</span>
														{/if}
													</div>
												</div>
											{/each}
										</div>

										<div class="mt-3 flex justify-end gap-2">
											{#if editingId === item.id}
												<button type="button" class="rounded border border-slate-300 px-3 py-1.5 text-sm font-semibold" onclick={() => (editingId = null)}>Cancel</button>
												<button type="button" class="rounded bg-blue-700 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50" disabled={saving} onclick={() => void saveItem(item)}>{saving ? 'Saving…' : 'Save item'}</button>
											{:else}
												<button type="button" class="rounded border border-slate-300 px-3 py-1.5 text-sm font-semibold" onclick={() => (editingId = item.id)}>✎ Edit</button>
											{/if}
										</div>
									</div>
								</div>
							</article>
						{/each}
					</div>

					<div class="mt-5 rounded-xl bg-slate-50 p-4">
						<p class="text-xs font-semibold uppercase tracking-wide text-slate-500">Coverage</p>
						<div class="mt-2 flex flex-wrap gap-2">
							{#each Object.entries(card.coverage) as [id, count]}
								<span class={`rounded-full px-2.5 py-1 text-xs font-semibold ${count > 0 ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-900'}`}>{id} {count > 0 ? '✓'.repeat(Math.min(count, 3)) : '0'}</span>
							{/each}
						</div>
					</div>

					<div class="mt-5 flex justify-center">
						<button
							type="button"
							class="rounded-lg border border-blue-300 bg-white px-4 py-2 text-sm font-semibold text-blue-800 disabled:opacity-50"
							disabled={regenerating || saving}
							onclick={() => void regenerate()}
						>{regenerating ? 'Regenerating…' : 'Regenerate this card’s quiz'}</button>
					</div>
				</section>
			{/if}

			{#if error}
				<p class="mt-4 text-sm text-red-700" role="alert">{error}</p>
			{/if}
		{/if}
	</section>
</main>
