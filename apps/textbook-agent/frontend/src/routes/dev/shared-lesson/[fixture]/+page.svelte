<script lang="ts">
	import { page } from '$app/state';
	import { isLearnDocument, type LearnDocument } from '$lib/learn/document/types';
	import StudentLessonShell from '$lib/learn/student/StudentLessonShell.svelte';

	let { data }: { data: { document: unknown } } = $props();
	const document = $derived(
		isLearnDocument(data.document)
			? ({
					...(data.document as LearnDocument),
					nodes: (data.document as LearnDocument).nodes.map((node) =>
						node.kind === 'figure' && node.asset_id === 'fixture-seedlings'
							? { ...node, asset_id: '/dev/shared-lesson-asset/seedlings.svg' }
							: node
					)
				} as LearnDocument)
			: null
	);
</script>

<svelte:head>
	<title>{document?.title ?? 'Shared lesson fixture'}</title>
</svelte:head>

<main class="fixture-page" data-fixture={page.params.fixture}>
	{#if document}
		<StudentLessonShell {document} preview />
	{:else}
		<p class="status">Fixture payload is not a LearnDocument v2 artifact.</p>
	{/if}
</main>

<style>
	.fixture-page {
		min-height: 100vh;
		background: var(--paper);
		color: var(--ink);
	}
	.status {
		max-width: 1080px;
		margin: 24px auto;
		padding: 0 18px;
	}
</style>
