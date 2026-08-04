<script lang="ts">
	interface SectionLike {
		header: { title: string };
		hook: { headline: string };
	}

	interface Props {
		section: SectionLike;
	}

	let { section }: Props = $props();
</script>

<article data-testid="mock-template-render">
	<h2>{section.header.title}</h2>
	<p>{section.hook.headline}</p>
</article>
