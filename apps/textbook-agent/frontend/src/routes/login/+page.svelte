<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { fromStore } from 'svelte/store';
	import { exchangeGoogleToken } from '$lib/api/auth';
	import { isApiError } from '$lib/api/errors';
	import { mountGoogleSignIn } from '$lib/auth/google';
	import { navigateToLanding } from '$lib/auth/routing';
	import {
		googleClientIdMissingMessage,
		resolveGoogleClientId,
		type FrontendEnvironment
	} from '$lib/config/environment';
	import { authUser, setAuth } from '$lib/stores/auth';
	import type { User } from '$lib/types';

	let errorMessage: string | null = $state(null);
	let loading = $state(false);
	let redirecting = $state(false);
	const user = fromStore(authUser);

	async function redirectAuthenticatedUser(nextUser: User) {
		if (redirecting) {
			return;
		}

		redirecting = true;
		try {
			await navigateToLanding(nextUser, goto, {
				getCurrentPath: () => window.location.pathname,
				hardRedirect: (path) => {
					window.location.replace(path);
				}
			});
		} catch (error) {
			redirecting = false;
			loading = false;
			errorMessage =
				error instanceof Error ? error.message : 'Signed in, but navigation failed.';
		}
	}

	$effect(() => {
		if (user.current) {
			void redirectAuthenticatedUser(user.current);
		}
	});

	onMount(() => {
		if (user.current) {
			return;
		}

		const clientId = resolveGoogleClientId(import.meta.env as FrontendEnvironment);
		if (!clientId) {
			errorMessage = googleClientIdMissingMessage();
			return;
		}

		const buttonElement = document.getElementById('google-signin-btn');
		if (!(buttonElement instanceof HTMLElement)) {
			errorMessage = 'Google sign-in could not be initialized.';
			return;
		}

		let cleanup: (() => void) | undefined;
		void mountGoogleSignIn({
			clientId,
			buttonElement,
			onCredential: handleCredentialResponse
		})
			.then((dispose) => {
				cleanup = dispose;
			})
			.catch((error) => {
				errorMessage =
					error instanceof Error ? error.message : 'Failed to initialize Google sign-in.';
			});

		return () => {
			cleanup?.();
		};
	});

	async function handleCredentialResponse(response: { credential: string }) {
		loading = true;
		errorMessage = null;
		let authenticated = false;
		try {
			const authResponse = await exchangeGoogleToken(response.credential);
			setAuth(authResponse);
			authenticated = true;
		} catch (err) {
			if (isApiError(err)) {
				errorMessage = err.detail;
			} else {
				errorMessage = err instanceof Error ? err.message : 'Authentication failed.';
			}
			loading = false;
			return;
		} finally {
			loading = authenticated;
		}
	}
</script>

<div class="login-container">
	<div class="login-card">
		<h1>Textbook Agent</h1>
		<p>Sign in to set up your teacher workspace, plan lessons in Studio, and save reusable classroom defaults.</p>

		<div id="google-signin-btn" class="google-btn-wrapper"></div>

		{#if loading}
			<p class="loading">Signing in...</p>
		{:else}
			<p class="hint">Continue with your Google account using the button below.</p>
		{/if}

		{#if errorMessage}
			<p class="error">{errorMessage}</p>
		{/if}
	</div>
</div>

<style>
	.login-container {
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 80vh;
	}

	.login-card {
		text-align: center;
		max-width: 400px;
		padding: 2.5rem;
		border: 1px solid #333;
		border-radius: 12px;
		background: #1a1a1a;
	}

	h1 {
		margin-bottom: 0.5rem;
		font-size: 1.75rem;
	}

	p {
		color: #aaa;
		margin-bottom: 1.5rem;
	}

	.google-btn-wrapper {
		display: flex;
		justify-content: center;
		margin: 1.5rem 0;
	}

	.loading {
		color: #6d9eeb;
	}

	.hint {
		font-size: 0.9rem;
		color: #888;
	}

	.error {
		color: #e57373;
	}
</style>
