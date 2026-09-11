<script lang="ts">
	interface Props {
		document: { title?: string };
		lessonId?: string | null;
		previewHref?: string | null;
		onDocumentChange?: (doc: unknown) => void;
	}

	let { document }: Props = $props();
</script>

<div data-testid="mock-document-editor">{document.title}</div>
