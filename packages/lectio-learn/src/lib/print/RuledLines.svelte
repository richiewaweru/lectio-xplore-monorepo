<script lang="ts">
	let {
		lines = 4,
		lineHeight = '1.8rem',
		label = undefined
	}: { lines?: number; lineHeight?: string; label?: string } = $props();
</script>

<div class="ruled-lines">
	{#if label}
		<p class="label">{label}</p>
	{/if}
	<div class="lines-container">
		{#each Array.from({ length: lines }) as _}
			<div class="line" style="height: {lineHeight}"></div>
		{/each}
	</div>
</div>

<style>
	.ruled-lines {
		margin: 1rem 0;
	}

	.label {
		font-size: 0.875rem;
		font-weight: 600;
		margin-bottom: 0.5rem;
		color: #374151;
	}

	.lines-container {
		display: flex;
		flex-direction: column;
	}

	.line {
		border-bottom: 1px solid #d1d5db;
		margin-bottom: 0.25rem;
	}

	@media print {
		.line {
			border-bottom: 1px solid #9ca3af;
		}
	}
</style>
