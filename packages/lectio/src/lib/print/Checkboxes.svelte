<script lang="ts">
	let { count, size = '1rem' }: { count: number; size?: string } = $props();
</script>

<div class="checkboxes">
	{#each Array.from({ length: count }) as _}
		<div class="checkbox" style="width: {size}; height: {size}"></div>
	{/each}
</div>

<style>
	.checkboxes {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.checkbox {
		border: 2px solid #374151;
		border-radius: 0.125rem;
		flex-shrink: 0;
	}

	@media print {
		.checkbox {
			border-color: #000;
		}
	}
</style>
