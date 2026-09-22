<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { getProfile } from '$lib/api/profile';
	import { getOnboardingRoute } from '$lib/shared/auth/routing';
	import ProfileSummary from '$lib/components/workspace/ProfileSummary.svelte';
	import type { TeacherProfile } from '$lib/types';
	import { PageHeader, Card, InlineError } from '$lib/ui';

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

<a class="back-link" href="/units">← Units</a>
<PageHeader title="Settings" description="Teaching profile, preferences, and advanced AI instructions." />

<div class="settings-grid">
	<Card padding="md">
		<h2>Teaching Profile</h2>
		<p>Subject context, grade bands, and classroom defaults.</p>
		{#if errorMessage}
			<InlineError message={errorMessage} />
		{:else if profile}
			<ProfileSummary {profile} onEdit={() => goto(getOnboardingRoute({ edit: true }))} />
		{:else}
			<p class="muted">Loading your profile…</p>
		{/if}
	</Card>

	<Card padding="md" href="/settings/prompts">
		<h2>AI Instructions</h2>
		<p>Advanced prompt customization for how lessons get written. Keep this separate from everyday teaching settings.</p>
		<span class="cta">Open advanced prompts →</span>
	</Card>

	<Card padding="md">
		<h2>Account</h2>
		<p>Signed in with Google. Profile picture and name come from your account.</p>
	</Card>
</div>

<style>
	.back-link {
		display: inline-block;
		margin-bottom: var(--space-3);
		color: var(--ink-2);
		font-size: 0.875rem;
		text-decoration: none;
	}
	.back-link:hover {
		color: var(--ink);
	}
	.settings-grid {
		display: grid;
		gap: var(--space-4);
	}
	h2 {
		margin: 0 0 0.35rem;
		font-size: 1.05rem;
	}
	p {
		margin: 0 0 1rem;
		color: var(--ink-2);
		font-size: 0.875rem;
		line-height: 1.45;
	}
	.cta {
		color: var(--accent);
		font-size: 0.875rem;
		font-weight: 550;
	}
	.muted {
		color: var(--ink-2);
	}
</style>
