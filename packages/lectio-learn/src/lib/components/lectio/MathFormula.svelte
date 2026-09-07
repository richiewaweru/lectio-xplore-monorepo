<script lang="ts">
	import katex from 'katex';

	let {
		formula,
		displayMode = false,
		class: className = ''
	}: {
		formula: string;
		displayMode?: boolean;
		class?: string;
	} = $props();

	const rendered = $derived(
		katex.renderToString(formula, {
			displayMode,
			throwOnError: false,
			strict: 'ignore'
		})
	);
</script>

<div class={className}>
	{@html rendered}
</div>
