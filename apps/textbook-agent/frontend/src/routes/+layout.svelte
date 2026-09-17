<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { fromStore } from 'svelte/store';
	import { isPublicLearnerPath, resolveShellRedirect } from '$lib/shared/auth/routing';
	import { fetchCurrentUser } from '$lib/api/shared/auth';
	import { authInitialized, authIsAuthenticated, authUser, bootstrapAuth } from '$lib/shared/stores/auth';
	import { AppShell } from '$lib/ui';

	let { children } = $props();
	const initialized = fromStore(authInitialized);
	const user = fromStore(authUser);
	const authed = fromStore(authIsAuthenticated);

	const isStudioPrintRoute = $derived(
		page.url.pathname.startsWith('/studio/print/') && page.url.searchParams.get('print') === 'true'
	);
	const isBuilderPrintRoute = $derived(page.url.pathname.startsWith('/builder/print/'));
	const isPrintShellRoute = $derived(isStudioPrintRoute || isBuilderPrintRoute);
	const isLearnerChrome = $derived(isPublicLearnerPath(page.url.pathname));
	const isLoginOrOnboarding = $derived(
		page.url.pathname.startsWith('/login') || page.url.pathname.startsWith('/onboarding')
	);
	const showTeacherShell = $derived(
		!isPrintShellRoute && !isLearnerChrome && !isLoginOrOnboarding && authed.current
	);

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
	<link rel="preconnect" href="https://fonts.googleapis.com" />
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
	<link
		href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Mono:wght@500&family=Inter:wght@400;500;600&display=swap"
		rel="stylesheet"
	/>
	<title>Lectio</title>
</svelte:head>

{#if !initialized.current && !isPrintShellRoute}
	<p class="boot">Loading session…</p>
{:else if showTeacherShell}
	<AppShell user={user.current} pathname={page.url.pathname}>
		<main class="app-main">
			{@render children()}
		</main>
	</AppShell>
{:else}
	<main class="bare-main" class:print={isPrintShellRoute}>
		{@render children()}
	</main>
{/if}

<style>
	.boot {
		padding: 2rem;
		color: var(--ink-2);
	}
	.app-main {
		padding: var(--space-6) var(--space-8);
		max-width: 1200px;
	}
	.bare-main {
		min-height: 100vh;
		padding: var(--space-6);
		max-width: 720px;
		margin: 0 auto;
	}
	.bare-main.print {
		max-width: none;
		margin: 0;
		padding: 0;
	}
	@media (max-width: 860px) {
		.app-main {
			padding: var(--space-4);
		}
	}
</style>
