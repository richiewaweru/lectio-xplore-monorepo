<script lang="ts">
	import { browser } from '$app/environment';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import type { LessonDocument } from '@lectio/learn';
	import { loadBuilderLessonWithFallback } from '$lib/learn/authoring/builder/persistence/server-sync';
	import StudentLessonShell from '$lib/learn/student/StudentLessonShell.svelte';
	import { isApiError } from '$lib/api/errors';

	let ready = $state(false);
	let error = $state<string | null>(null);
	let document = $state<LessonDocument | null>(null);

	const id = $derived(page.params.id);

	onMount(async () => {
		if (!browser || !id) return;
		try {
			const result = await loadBuilderLessonWithFallback(id);
			document = result.document;
			ready = true;
		} catch (err) {
			if (isApiError(err)) {
				error = `${err.name}: ${err.detail}`;
			} else {
				error = err instanceof Error ? err.message : 'Failed to load lesson';
			}
			ready = true;
		}
	});
</script>

<main class="learn-preview-page">
	<div class="preview-banner">
		<p class="eyebrow">Student lesson shell</p>
		<p>
			Authoring stays in <a href={`/builder/${id}`}>Builder</a>. This view is a read-only stage experience —
			preview mode uses the same shell and interaction components and does not call
			<code>submit_attempt</code> / persist learner attempts.
		</p>
	</div>

	{#if !ready}
		<p class="status">Loading lesson…</p>
	{:else if error}
		<p class="status error">{error}</p>
	{:else if document}
		<StudentLessonShell {document} preview />
	{/if}
</main>

<style>
	.learn-preview-page {
		min-height: 100vh;
		background: var(--paper);
		color: var(--ink);
	}
	.preview-banner {
		max-width: 1080px;
		margin: 0 auto;
		padding: 20px 18px 0;
	}
	.eyebrow {
		margin: 0 0 6px;
		color: var(--ink-3);
		font: 500 11px 'IBM Plex Mono', monospace;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}
	.preview-banner p {
		margin: 0;
		color: var(--ink-2);
		font-size: 13px;
		line-height: 1.5;
	}
	.preview-banner a {
		color: var(--accent);
		font-weight: 600;
		text-decoration: none;
	}
	.status {
		max-width: 1080px;
		margin: 24px auto;
		padding: 0 18px;
		color: var(--ink-2);
	}
	.status.error {
		color: var(--amber, #b45309);
	}
</style>
