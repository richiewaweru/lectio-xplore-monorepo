<script lang="ts">
	import type { LectioDocument } from '$lib/contract/document';
	import SectionView from './SectionView.svelte';
	import BlockView from './BlockView.svelte';
	import '$lib/print/base-print.css';

	let {
		document: doc,
		edition = 'teacher'
	}: {
		document: LectioDocument;
		edition?: 'student' | 'teacher';
	} = $props();

	const front = $derived(doc.front_matter ?? { cover: true, contents: true, fields: ['Student Name', 'Date'] });
	const showCover = $derived(front.cover !== false);
	const showContents = $derived(front.contents !== false);
	const fields = $derived(front.fields ?? ['Student Name', 'Date']);
</script>

<article class="lectio-document" lang={doc.language} data-edition={edition}>
	{#if showCover}
		<header class="lectio-cover">
			<h1 class="lectio-cover-title">{doc.title}</h1>
			{#if doc.subject || doc.metadata?.school}
				<p class="lectio-cover-subtitle">
					{[doc.subject, doc.metadata?.school, doc.metadata?.teacher].filter(Boolean).join(' · ')}
				</p>
			{/if}
			<div class="lectio-cover-fields">
				{#each fields as field}
					<div class="lectio-cover-field">{field}</div>
				{/each}
			</div>
		</header>
	{/if}

	{#if showContents}
		<nav class="lectio-contents" aria-label="Contents">
			<h2>Contents</h2>
			{#each doc.sections as section}
				<div class="lectio-contents-entry">
					<span>{section.title}</span>
					<span></span>
				</div>
			{/each}
		</nav>
	{/if}

	<div class="lectio-page-flow">
		<div class="lectio-main">
			{#each doc.sections as section}
				<SectionView {section} />
			{/each}
		</div>
	</div>

	{#if edition === 'teacher' && doc.answer_key}
		<BlockView block={doc.answer_key} />
	{/if}
</article>
