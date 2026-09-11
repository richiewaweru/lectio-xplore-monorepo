<script lang="ts">
	import { browser } from '$app/environment';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { isApiError } from '$lib/api/errors';
	import { loadBuilderLessonWithFallback } from '$lib/learn/authoring/builder/persistence/server-sync';
	import DocumentEditor from '$lib/learn/document/DocumentEditor.svelte';
	import { isLearnDocument, type LearnDocument } from '$lib/learn/document/types';
	import { logout } from '$lib/shared/stores/auth';

	let loadPromise = $state<ReturnType<typeof loadBuilderLessonWithFallback> | null>(null);
	let loadError = $state<{ status: number; title: string; detail: string } | null>(null);

	const id = $derived(page.params.id);

	onMount(() => {
		if (!browser) return;
		const lessonId = page.params.id;
		if (!lessonId) {
			loadError = {
				status: 400,
				title: 'Missing lesson id',
				detail: 'No lesson id was present in the route.'
			};
			return;
		}
		loadPromise = loadBuilderLessonWithFallback(lessonId).then((result) => {
			if (!result.document) {
				throw Object.assign(new Error('Lesson not found'), { status: 404 });
			}
			if (!isLearnDocument(result.document)) {
				throw Object.assign(new Error('Legacy lesson retired'), { status: 410 });
			}
			return result;
		});
	});
</script>

{#if loadError}
	<section class="mx-auto max-w-3xl p-6">
		<div class="rounded-xl border border-red-200 bg-red-50 p-5 text-red-800">
			<p class="text-xs font-semibold uppercase tracking-wide text-red-700">{loadError.status}</p>
			<h1 class="mt-1 text-xl font-bold">{loadError.title}</h1>
			<p class="mt-2 text-sm">{loadError.detail}</p>
		</div>
	</section>
{:else if !loadPromise}
	<section class="mx-auto max-w-4xl p-6" aria-busy="true">
		<p class="text-sm text-slate-500">Preparing lesson workspace...</p>
	</section>
{:else}
	{#await loadPromise}
		<section class="mx-auto max-w-4xl p-6" aria-busy="true" aria-live="polite">
			<p class="mt-4 text-sm text-slate-500">Loading lesson workspace...</p>
		</section>
	{:then result}
		<main class="mx-auto max-w-4xl p-6">
			{#if result.source === 'idb'}
				<p class="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
					Loaded local cached copy. Server sync will resume when connectivity is restored.
				</p>
			{/if}
			<p class="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
				LearnDocument v2 editor
			</p>
			<DocumentEditor
				document={result.document as LearnDocument}
				lessonId={id}
				previewHref={id ? `/learn/lessons/${id}` : null}
			/>
		</main>
	{:catch error}
		<section class="mx-auto max-w-3xl p-6">
			<div class="rounded-xl border border-red-200 bg-red-50 p-5 text-red-800">
				{#if isApiError(error) && error.status === 401}
					<p class="text-sm">Session expired.</p>
					<button
						class="mt-3 rounded border px-3 py-1"
						onclick={() => {
							logout();
							void goto('/login', { replaceState: true });
						}}>Sign in</button
					>
				{:else}
					<p class="text-xs font-semibold uppercase tracking-wide text-red-700">
						{(error as { status?: number }).status ?? 500}
					</p>
					<h1 class="mt-1 text-xl font-bold">Unable to load lesson</h1>
					<p class="mt-2 text-sm">
						{error instanceof Error ? error.message : 'Please retry in a moment.'}
					</p>
				{/if}
			</div>
		</section>
	{/await}
{/if}
