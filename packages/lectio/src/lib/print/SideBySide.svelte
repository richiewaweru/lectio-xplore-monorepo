<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		leftLabel,
		rightLabel,
		left,
		right
	}: {
		leftLabel: string;
		rightLabel: string;
		left: Snippet;
		right: Snippet;
	} = $props();
</script>

<div class="side-by-side">
	<div class="side">
		<div class="label">{leftLabel}</div>
		<div class="content">
			{@render left()}
		</div>
	</div>

	<div class="side">
		<div class="label">{rightLabel}</div>
		<div class="content">
			{@render right()}
		</div>
	</div>
</div>

<style>
	.side-by-side {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 2rem;
		margin: 1rem 0;
		page-break-inside: avoid;
	}

	.label {
		font-weight: 600;
		margin-bottom: 0.5rem;
		text-align: center;
	}

	.content {
		display: flex;
		justify-content: center;
	}

	@media print {
		.side-by-side {
			gap: 1rem;
		}
	}
</style>
