<script lang="ts">
	import { page } from '$app/stores';
	import favicon from '$lib/assets/favicon.svg';
	import '../app.css';

	let { children } = $props();

	const printMode = $derived($page.url.searchParams.get('print') === '1');
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>@lectio/page — print-native documents</title>
</svelte:head>

{#if printMode}
	{@render children()}
{:else}
	<div class="app-shell">
		<header class="app-header">
			<a href="/" class="brand">@lectio/page</a>
			<nav>
				<a href="/">Deliverables</a>
				<a href="/fixtures">Fixtures</a>
				<a href="/objects">Objects</a>
			</nav>
		</header>
		<main>
			{@render children()}
		</main>
	</div>
{/if}

<style>
	:global(body) {
		margin: 0;
		font-family: 'Public Sans', system-ui, sans-serif;
		background: #f3f3f1;
		color: #111;
	}
	.app-shell {
		min-height: 100vh;
	}
	.app-header {
		display: flex;
		gap: 1.5rem;
		align-items: center;
		padding: 0.85rem 1.25rem;
		background: #111;
		color: #f5f5f5;
	}
	.brand {
		font-weight: 700;
		color: inherit;
		text-decoration: none;
		letter-spacing: 0.02em;
	}
	nav {
		display: flex;
		gap: 1rem;
	}
	nav a {
		color: #ddd;
		text-decoration: none;
		font-size: 0.95rem;
	}
	nav a:hover {
		color: #fff;
	}
	main {
		padding: 1.25rem;
	}
</style>
