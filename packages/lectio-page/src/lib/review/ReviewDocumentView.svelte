<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { LectioDocument } from '$lib/contract/document';
	import LectioDocumentView from '../render/LectioDocumentView.svelte';
	import '$lib/print/screen.css';

	let {
		document: doc,
		edition = 'teacher',
		children
	}: {
		document: LectioDocument;
		edition?: 'student' | 'teacher';
		children?: Snippet;
	} = $props();
</script>

<div class="lectio-review-frame">
	{#if children}
		<aside class="lectio-review-chrome">
			{@render children()}
		</aside>
	{/if}
	<div class="lectio-print-subtree">
		<LectioDocumentView document={doc} {edition} />
	</div>
</div>
