<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	onMount(() => {
		void goto('/units', { replaceState: true });
	});
</script>

<svelte:head><title>Units · Lectio</title></svelte:head>

<p role="status">Redirecting to your units…</p>
