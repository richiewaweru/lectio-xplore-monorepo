<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { fromStore } from 'svelte/store';
	import { resolveShellRedirect } from '$lib/auth/routing';
	import { fetchCurrentUser } from '$lib/api/auth';
	import { getCapabilities } from '$lib/api/capabilities';
	import { authInitialized, authIsAuthenticated, authUser, bootstrapAuth } from '$lib/stores/auth';

	let { children } = $props();
	const initialized = fromStore(authInitialized);
	const user = fromStore(authUser);
	const authed = fromStore(authIsAuthenticated);
	let xploreV2 = $state(false);
	let capabilitiesReady = $state(false);

	const isStudioPrintRoute = $derived(
		page.url.pathname.startsWith('/studio/print/') && page.url.searchParams.get('print') === 'true'
	);
	const isBuilderPrintRoute = $derived(page.url.pathname.startsWith('/builder/print/'));
	const isPrintShellRoute = $derived(isStudioPrintRoute || isBuilderPrintRoute);
	const isLessonsRoute = $derived(page.url.pathname.startsWith('/lessons'));
	const isUnitsRoute = $derived(page.url.pathname.startsWith('/units'));
	const isWorkspaceRoute = $derived(isLessonsRoute || isUnitsRoute);

	onMount(() => {
		void bootstrapAuth(fetchCurrentUser).then(async (currentUser) => {
			if (currentUser) {
				try { xploreV2 = (await getCapabilities()).xplore_v2; } catch { xploreV2 = false; }
			}
			capabilitiesReady = true;
		});
	});

	$effect(() => {
		if (!initialized.current || isPrintShellRoute) return;
		const path = page.url.pathname;
		const redirectTo = resolveShellRedirect(user.current, path);
		if (redirectTo && redirectTo !== path) {
			goto(redirectTo, { replaceState: true });
		}
		if (capabilitiesReady && path.startsWith('/units') && !xploreV2) {
			goto('/lessons', { replaceState: true });
		}
	});
</script>

<svelte:head>
	<link rel="preconnect" href="https://fonts.googleapis.com" />
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
	<link
		href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Mono:wght@500&family=Inter:wght@400;500;600&display=swap"
		rel="stylesheet"
	/>
	<title>Lectio</title>
</svelte:head>

{#if !isPrintShellRoute}
	<header class="workspace-header">
		<nav class="workspace-nav">
			<a href={authed.current ? '/lessons' : '/'} class="workspace-brand">Lect<span>i</span>o</a>
			{#if authed.current && user.current}
				<div class="workspace-links" aria-label="Workspace">
					<a href="/lessons" aria-current={isLessonsRoute ? 'page' : undefined}>Home</a>
					{#if xploreV2}<a href="/units" aria-current={isUnitsRoute ? 'page' : undefined}>Units</a>{/if}
					<a href="/studio">Legacy</a>
				</div>
				<div class="workspace-nav-end">
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

<main class:workspace-main={isWorkspaceRoute}>
	{#if initialized.current || isPrintShellRoute}
		{@render children()}
	{:else}
		<p>Loading session...</p>
	{/if}
</main>

<style>
	:global(:root) {
		--paper: #f7f8f6;
		--surface: #ffffff;
		--rule: #e3e6e1;
		--ink: #16211c;
		--ink-2: #5c6b63;
		--ink-3: #8b978f;
		--accent: #1c5d45;
		--accent-soft: #e7f0ea;
		--amber: #9a6b12;
		--amber-soft: #fbf0da;
	}

	:global(body) {
		margin: 0;
		background: var(--paper);
		color: var(--ink);
		font-family: Inter, sans-serif;
	}

	.workspace-header {
		position: sticky;
		top: 0;
		z-index: 20;
		height: 58px;
		box-sizing: border-box;
		border-bottom: 1px solid var(--rule);
		padding: 0 28px;
		background: color-mix(in srgb, var(--paper) 94%, transparent);
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
		color: var(--ink);
		font-family: Fraunces, Georgia, serif;
		font-size: 20px;
		font-weight: 600;
		letter-spacing: -0.03em;
		text-decoration: none;
	}

	.workspace-brand span {
		color: var(--accent);
	}

	.workspace-nav-end {
		display: flex;
		align-items: center;
		gap: 14px;
	}

	.workspace-links {
		display: flex;
		align-items: center;
		gap: 4px;
	}

	.workspace-links a {
		border-radius: 6px;
		color: var(--ink-2);
		font-size: 13px;
		font-weight: 500;
		padding: 7px 10px;
		text-decoration: none;
	}

	.workspace-links a:hover,
	.workspace-links a:focus-visible,
	.workspace-links a[aria-current='page'] {
		background: var(--accent-soft);
		color: var(--accent);
	}

	.workspace-links a:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
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
		outline: 2px solid var(--accent);
		outline-offset: 3px;
	}

	.workspace-initials {
		display: grid;
		place-items: center;
		background: var(--accent);
		color: var(--surface);
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

		.workspace-links a {
			padding: 7px;
		}

		.workspace-links a:last-child {
			display: none;
		}
	}
</style>
