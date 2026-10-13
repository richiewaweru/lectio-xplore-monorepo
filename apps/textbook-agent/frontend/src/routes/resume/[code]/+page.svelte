<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { Card, InlineError } from '$lib/ui';
	import { resumeWithCode } from '$lib/learn/student/api/resume';

	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			const learnerId = await resumeWithCode(decodeURIComponent(page.params.code ?? ''));
			await goto(`/learn/home/${encodeURIComponent(learnerId)}`, { replaceState: true });
		} catch (err) {
			error = err instanceof Error ? err.message : 'Something went wrong. Try again.';
		}
	});
</script>

<div class="resume">
	<Card padding="lg">
		{#if error}
			<h1>We could not open that code</h1>
			<InlineError message={error} />
			<p><a href="/join">Go to the join page</a></p>
		{:else}
			<p class="lede">Getting your lessons…</p>
		{/if}
	</Card>
</div>

<style>
	.resume {
		min-height: 100vh;
		display: grid;
		place-items: center;
		padding: 1.5rem;
		background: var(--paper);
	}
	h1 {
		margin: 0 0 0.75rem;
		font-family: var(--font-serif);
		font-size: 1.5rem;
	}
	.lede {
		margin: 0;
		color: var(--ink-2);
	}
</style>
