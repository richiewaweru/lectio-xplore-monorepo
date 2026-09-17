<script lang="ts">
	interface Props {
		message: string;
		hint?: string;
	}

	let { message, hint }: Props = $props();
</script>

<div class="err" role="alert">
	<strong>{message}</strong>
	{#if hint}
		<p>{hint}</p>
	{/if}
</div>

<style>
	.err {
		padding: var(--space-3) var(--space-4);
		border-radius: var(--radius-md);
		background: var(--danger-soft);
		border: 1px solid color-mix(in srgb, var(--danger) 18%, transparent);
		color: var(--danger);
	}
	strong {
		font-size: 0.875rem;
	}
	p {
		margin: 0.25rem 0 0;
		font-size: 0.8125rem;
		opacity: 0.9;
	}
</style>
