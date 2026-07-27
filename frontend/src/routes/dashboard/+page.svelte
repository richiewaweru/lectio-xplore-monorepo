<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	onMount(() => {
		void goto('/lessons', { replaceState: true });
	});
</script>

<svelte:head><title>Lessons · Lectio</title></svelte:head>

<p role="status">Redirecting to your lessons…</p>
