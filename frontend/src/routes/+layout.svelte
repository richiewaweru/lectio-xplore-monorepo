<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { fromStore } from 'svelte/store';
	import { resolveShellRedirect } from '$lib/auth/routing';
	import { fetchCurrentUser } from '$lib/api/auth';
	import { authInitialized, authIsAuthenticated, authUser, bootstrapAuth, logout } from '$lib/stores/auth';

	let { children } = $props();
	const initialized = fromStore(authInitialized);
	const user = fromStore(authUser);
	const authed = fromStore(authIsAuthenticated);
	
	const isPrintStudioRoute = $derived(
		page.url.pathname.startsWith('/studio/print/') && page.url.searchParams.get('print') === 'true'
	);
	const isPrintShellRoute = $derived(isPrintStudioRoute);
	const isLessonsRoute = $derived(page.url.pathname.startsWith('/lessons'));

	onMount(() => {
		void bootstrapAuth(fetchCurrentUser);
	});

	$effect(() => {
		if (!initialized.current) return;
		const path = page.url.pathname;
		if (isPrintShellRoute) {
			return;
		}

		const redirectTo = resolveShellRedirect(user.current, path);
		if (redirectTo && redirectTo !== path) {
			goto(redirectTo, { replaceState: true });
		}
	});

	function handleLogout() {
		logout();
		goto('/login', { replaceState: true });
	}
</script>

<svelte:head>
	<title>Textbook Agent</title>
</svelte:head>

{#if !isPrintShellRoute && isLessonsRoute}
	<header class="workspace-header">
		<nav class="workspace-nav">
			<a href="/lessons" class="workspace-brand">Lect<span>i</span>o</a>
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
{:else if !isPrintShellRoute}
	<header>
		<nav>
			<div class="nav-left">
				<a href={authed.current ? '/dashboard' : '/'} class="brand">Textbook Agent</a>
				{#if authed.current && user.current}
					<div class="nav-links">
						<a href="/dashboard" class="nav-link">Dashboard</a>
						<a href="/studio" class="nav-link">Studio</a>
						<a href="/builder" class="nav-link">Builder</a>
						<a href="/builder/new" class="nav-link">New Lesson</a>
					</div>
				{/if}
			</div>
			{#if authed.current && user.current}
				<div class="nav-right">
					{#if user.current.picture_url}
						<img src={user.current.picture_url} alt={user.current.name ?? ''} class="avatar" />
					{/if}
					<span class="user-name">{user.current.name ?? user.current.email}</span>
					<button onclick={handleLogout} class="logout-btn">Sign out</button>
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

	header {
		border-bottom: 1px solid rgba(61, 47, 26, 0.15);
		padding: 0.75rem 1.5rem;
		backdrop-filter: blur(12px);
		background: rgba(250, 245, 235, 0.82);
	}

	nav {
		display: flex;
		align-items: center;
		justify-content: space-between;
		max-width: 1200px;
		margin: 0 auto;
	}

	.nav-left,
	.nav-links,
	.nav-right {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.brand {
		font-weight: 700;
		font-size: 1.1rem;
		color: #1f2b34;
		text-decoration: none;
	}

	.nav-link {
		color: #5f574d;
		text-decoration: none;
		font-size: 0.92rem;
	}

	.avatar {
		width: 28px;
		height: 28px;
		border-radius: 50%;
	}

	.user-name {
		font-size: 0.9rem;
		color: #5f574d;
	}

	.logout-btn {
		background: rgba(31, 43, 52, 0.05);
		border: 1px solid rgba(31, 43, 52, 0.15);
		color: #24343f;
		padding: 0.25rem 0.75rem;
		border-radius: 999px;
		cursor: pointer;
		font-size: 0.8rem;
	}

	.logout-btn:hover {
		border-color: rgba(31, 43, 52, 0.35);
		color: #111;
	}

	main {
		max-width: 1200px;
		margin: 0 auto;
		padding: 1.5rem;
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
		height: 100%;
		max-width: none;
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

	main.workspace-main {
		max-width: none;
		margin: 0;
		padding: 0;
	}

	@media (max-width: 720px) {
		nav,
		.nav-left,
		.nav-links,
		.nav-right {
			flex-wrap: wrap;
		}
	}
</style>
