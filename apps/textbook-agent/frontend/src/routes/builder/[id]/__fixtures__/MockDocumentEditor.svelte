<script lang="ts">
	interface Props {
		document: { title?: string };
		lessonId?: string | null;
		previewHref?: string | null;
		onDocumentChange?: (doc: unknown) => void;
		focusSectionId?: string | null;
	}

	let { document, focusSectionId = null }: Props = $props();
</script>

<div data-testid="mock-document-editor" data-focus-section={focusSectionId ?? ''}>{document.title}</div>
