<script lang="ts">
	import InlineMarkup from '$lib/learn/document/renderers/InlineMarkup.svelte';
	interface Props { title: string; index: number; total: number; }
	let { title, index, total }: Props = $props();
</script>

<header class="section-header">
	<p class="eyebrow">Part {index} of {total}</p>
	<h2><InlineMarkup value={title} /></h2>
</header>

<style>
	.section-header { border-top: 2px solid var(--ink, #1c2321); padding-top: 14px; }
	.eyebrow { margin: 0 0 8px; color: var(--muted, #5b6460); font-size: 14px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
	h2 { margin: 0; color: var(--ink, #1c2321); font: 700 30px/1.2 var(--font-serif, Fraunces, Georgia, serif); letter-spacing: -.02em; text-wrap: balance; }
</style>
