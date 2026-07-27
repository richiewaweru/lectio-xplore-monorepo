<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { fromStore } from 'svelte/store';
	import { resolveShellRedirect } from '$lib/auth/routing';
	import { fetchCurrentUser } from '$lib/api/auth';
	import { authInitialized, authIsAuthenticated, authUser, bootstrapAuth } from '$lib/stores/auth';

	let { children } = $props();
	const initialized = fromStore(authInitialized);
	const user = fromStore(authUser);
	const authed = fromStore(authIsAuthenticated);

	const isStudioPrintRoute = $derived(
		page.url.pathname.startsWith('/studio/print/') && page.url.searchParams.get('print') === 'true'
	);
	const isBuilderPrintRoute = $derived(page.url.pathname.startsWith('/builder/print/'));
	const isPrintShellRoute = $derived(isStudioPrintRoute || isBuilderPrintRoute);
	const isLessonsRoute = $derived(page.url.pathname.startsWith('/lessons'));

	onMount(() => {
		void bootstrapAuth(fetchCurrentUser);
	});

	$effect(() => {
		if (!initialized.current || isPrintShellRoute) return;
		const path = page.url.pathname;
		const redirectTo = resolveShellRedirect(user.current, path);
		if (redirectTo && redirectTo !== path) {
			goto(redirectTo, { replaceState: true });
		}
	});
</script>

<svelte:head>
	<title>Lectio</title>
</svelte:head>

{#if !isPrintShellRoute}
	<header class="workspace-header">
		<nav class="workspace-nav">
			<a href={authed.current ? '/lessons' : '/'} class="workspace-brand">Lect<span>i</span>o</a>
			{#if authed.current && user.current}
				<div class="workspace-nav-end">
					<span class="workspace-kbd" aria-hidden="true">⌘K</span>
					<a class="workspace-avatar-link" href="/settings" aria-label="Settings">
						{#if user.current.picture_url}
							<img src={user.current.picture_url} alt="" class="workspace-avatar" />
						{:else}
							<span class="workspace-avatar workspace-initials" title={user.current.name ?? user.current.email}>
								{(user.current.name ?? user.current.email).slice(0, 2).toUpperCase()}
							</span>
						{/if}
					</a>
				</div>
			{/if}
		</nav>
	</header>
{/if}

<main class:workspace-main={isLessonsRoute}>
	{#if initialized.current || isPrintShellRoute}
		{@render children()}
	{:else}
		<p>Loading session...</p>
	{/if}
</main>

<style>
	:global(body) {
		margin: 0;
		font-family:
			'Iowan Old Style', 'Palatino Linotype', 'Book Antiqua', Palatino, Georgia, serif;
		background:
			radial-gradient(circle at top, rgba(214, 196, 160, 0.22), transparent 32%),
			linear-gradient(180deg, #f4efe4 0%, #ece3d1 52%, #e4d7c0 100%);
		color: #1e1b16;
	}

	.workspace-header {
		position: sticky;
		top: 0;
		z-index: 20;
		height: 58px;
		box-sizing: border-box;
		border-bottom: 1px solid #e3e6e1;
		padding: 0 28px;
		background: rgba(247, 248, 246, 0.94);
		backdrop-filter: blur(10px);
	}

	.workspace-nav {
		display: flex;
		height: 100%;
		align-items: center;
		justify-content: space-between;
		margin: 0 auto;
	}

	.workspace-brand {
		color: #16211c;
		font-family: Fraunces, Georgia, serif;
		font-size: 20px;
		font-weight: 600;
		letter-spacing: -0.03em;
		text-decoration: none;
	}

	.workspace-brand span {
		color: #1c5d45;
	}

	.workspace-nav-end {
		display: flex;
		align-items: center;
		gap: 14px;
	}

	.workspace-kbd {
		border: 1px solid #e3e6e1;
		border-radius: 5px;
		background: #fff;
		color: #8b978f;
		font: 500 11px 'IBM Plex Mono', monospace;
		padding: 3px 7px;
	}

	.workspace-avatar {
		width: 30px;
		height: 30px;
		border-radius: 50%;
		object-fit: cover;
	}

	.workspace-avatar-link {
		display: inline-flex;
		border-radius: 50%;
	}

	.workspace-avatar-link:focus-visible {
		outline: 2px solid #1c5d45;
		outline-offset: 3px;
	}

	.workspace-initials {
		display: grid;
		place-items: center;
		background: #1c5d45;
		color: #fff;
		font: 600 11px Inter, sans-serif;
	}

	main {
		max-width: 1200px;
		margin: 0 auto;
		padding: 1.5rem;
	}

	main.workspace-main {
		max-width: none;
		margin: 0;
		padding: 0;
	}

	@media (max-width: 640px) {
		.workspace-header {
			padding: 0 18px;
		}
	}
</style>
