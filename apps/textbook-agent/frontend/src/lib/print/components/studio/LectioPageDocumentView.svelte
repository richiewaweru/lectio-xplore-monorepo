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

	/** Mark each rendered section so editors can scroll to and highlight it. */
	function tagSections(node: HTMLElement) {
		const apply = () => {
			for (const element of node.querySelectorAll<HTMLElement>('.lectio-section[id]')) {
				element.dataset.sectionId = element.id;
			}
		};
		apply();
		const observer = new MutationObserver(apply);
		observer.observe(node, { childList: true, subtree: true });
		return { destroy: () => observer.disconnect() };
	}
</script>

<div class="lectio-page-v2" data-document-version="2" data-edition={edition} use:tagSections>
	<LectioDocumentView document={doc} {edition} />
</div>
