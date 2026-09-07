<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import AppSidebar from '$lib/navigation/AppSidebar.svelte';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Lectio - Educational Component Library</title>
</svelte:head>

<div class="min-h-screen bg-transparent">
	<div class="mx-auto flex min-h-screen max-w-[96rem] items-start gap-6 px-3 py-3 sm:px-4 lg:px-5">
		<AppSidebar frameworkLabel="SvelteKit" />

		<main class="min-h-screen min-w-0 flex-1">
			{@render children()}
		</main>
	</div>
</div>
