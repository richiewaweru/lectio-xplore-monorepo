<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { getProfile } from '$lib/api/profile';
	import { getOnboardingRoute } from '$lib/auth/routing';
	import ProfileSummary from '$lib/components/workspace/ProfileSummary.svelte';
	import type { TeacherProfile } from '$lib/types';

	let profile = $state<TeacherProfile | null>(null);
	let errorMessage = $state<string | null>(null);

	onMount(async () => {
		try {
			profile = await getProfile();
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'Failed to load your profile.';
		}
	});
</script>

<svelte:head><title>Settings · Lectio</title></svelte:head>

<div class="settings-page">
	<header>
		<p class="eyebrow">Settings</p>
		<h1>Teacher profile</h1>
	</header>
	{#if errorMessage}
		<p class="error" role="alert">{errorMessage}</p>
	{:else if profile}
		<ProfileSummary {profile} onEdit={() => goto(getOnboardingRoute({ edit: true }))} />
	{:else}
		<p role="status">Loading your profile…</p>
	{/if}
</div>

<style>
	.settings-page {
		display: grid;
		gap: 1.5rem;
		max-width: 860px;
		margin: 0 auto;
	}

	.eyebrow {
		margin: 0 0 0.3rem;
		color: #6b7c88;
		font-size: 0.78rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
	}

	h1 {
		margin: 0;
	}

	.error {
		color: #864635;
	}
</style>
