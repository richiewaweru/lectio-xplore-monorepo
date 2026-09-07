<script lang="ts">
	import LectioDocumentView from '@lectio/page/LectioDocumentView.svelte';
	import type { LectioDocument } from '@lectio/page/contract';
	import '@lectio/page/print/base-print.css';

	let {
		document: doc,
		edition = 'teacher'
	}: {
		document: LectioDocument;
		edition?: 'teacher' | 'student';
	} = $props();
</script>

<div class="lectio-page-v2" data-document-version="2" data-edition={edition}>
	<LectioDocumentView document={doc} {edition} />
</div>
