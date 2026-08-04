<script lang="ts">
	import { providePrintMode } from 'lectio';
	import LectioDocumentView from '../LectioDocumentView.svelte';
	import type { GenerationDocument } from '$lib/types';

	interface Props {
		document: GenerationDocument;
	}

	let { document }: Props = $props();

	providePrintMode(() => true);
</script>

<LectioDocumentView {document} />
