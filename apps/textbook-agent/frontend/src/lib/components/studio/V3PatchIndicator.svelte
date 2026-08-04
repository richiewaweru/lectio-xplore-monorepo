<script lang="ts">
	import { onMount } from 'svelte';

	let visible = $state(true);

	onMount(() => {
		const timer = setTimeout(() => {
			visible = false;
		}, 2000);
		return () => clearTimeout(timer);
	});
</script>

{#if visible}
	<span class="v3-patch-indicator text-xs font-medium text-emerald-600" aria-label="Refined"> refined </span>
{/if}

<style>
	.v3-patch-indicator {
		animation: v3-patch-fade 2s ease forwards;
	}
	@keyframes v3-patch-fade {
		0% {
			opacity: 1;
		}
		70% {
			opacity: 1;
		}
		100% {
			opacity: 0;
		}
	}
</style>
