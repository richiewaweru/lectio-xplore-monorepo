<script lang="ts">
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { apiFetch } from '$lib/api/client';
	import { ensureOk } from '$lib/api/errors';
	import StudentLessonShell from '$lib/learn/student/StudentLessonShell.svelte';
	import {
		latestAttemptByInteraction,
		newSubmissionId,
		submitInstanceAttempt,
		type StoredAttempt
	} from '$lib/learn/student/api/attempts';
	import type { LessonDocument } from '@lectio/learn';

	let ready = $state(false);
	let error = $state<string | null>(null);
	let document = $state<LessonDocument | null>(null);
	let status = $state('active');
	let scoreLine = $state('');
	let currentSectionId = $state<string | null>(null);
	let activeIndex = $state(0);
	let releaseId = $state<string | null>(null);
	let attemptsByInteraction = $state(new Map<string, StoredAttempt>());

	const instanceId = $derived(page.params.instanceId);

	async function refreshInstance() {
		if (!instanceId) return;
		const headers: Record<string, string> = {};
		const token = localStorage.getItem('x-learner-session');
		if (token) headers['X-Learner-Session'] = token;
		const response = await apiFetch(`/api/v1/learn/instances/${instanceId}`, { headers });
		await ensureOk(response);
		const instance = await response.json();
		status = instance.status;
		scoreLine = `graded ${instance.graded?.score_earned ?? instance.score_earned}/${instance.graded?.score_possible ?? instance.score_possible} · practice ${instance.practice?.score_earned ?? 0}/${instance.practice?.score_possible ?? 0}`;
		currentSectionId = instance.current_section_id ?? null;
		releaseId = instance.learn_release_id;
		attemptsByInteraction = latestAttemptByInteraction(
			(instance.attempts ?? []) as StoredAttempt[]
		);
		return instance;
	}

	onMount(async () => {
		if (!browser || !instanceId) return;
		try {
			const instance = await refreshInstance();
			const headers: Record<string, string> = {};
			const token = localStorage.getItem('x-learner-session');
			if (token) headers['X-Learner-Session'] = token;
			const releaseResp = await apiFetch(`/api/v1/learn/releases/${instance.learn_release_id}`, {
				headers
			});
			await ensureOk(releaseResp);
			const release = await releaseResp.json();
			document = release.document as LessonDocument;
			if (document && currentSectionId) {
				const idx = document.sections.findIndex((s) => s.id === currentSectionId);
				if (idx >= 0) activeIndex = idx;
			}
			ready = true;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load instance';
			ready = true;
		}
	});

	async function onActiveIndexChange(index: number) {
		activeIndex = index;
		if (!document || !instanceId) return;
		const section = document.sections[index];
		if (!section) return;
		const headers: Record<string, string> = { 'Content-Type': 'application/json' };
		const token = localStorage.getItem('x-learner-session');
		if (token) headers['X-Learner-Session'] = token;
		await apiFetch(`/api/v1/learn/instances/${instanceId}/resume`, {
			method: 'POST',
			headers,
			body: JSON.stringify({ section_id: section.id, mark_visited: true })
		});
	}

	async function onSubmitAttempt(args: {
		interactionId: string;
		sectionId: string;
		response: Record<string, unknown>;
	}) {
		if (!instanceId) throw new Error('Missing instance');
		const result = await submitInstanceAttempt(instanceId, {
			interaction_id: args.interactionId,
			client_submission_id: newSubmissionId('seq'),
			response_json: args.response,
			section_id: args.sectionId,
			expected_release_id: releaseId ?? undefined
		});
		await refreshInstance();
		return {
			outcome: result.outcome,
			feedback: result.feedback,
			score_earned: result.score_earned,
			score_possible: result.score_possible
		};
	}
</script>

<main class="instance-page">
	<div class="banner">
		<p class="eyebrow">Learning instance · {status}</p>
		<p class="lede">Score {scoreLine}. Resume persists current section.</p>
		{#if status === 'completed'}
			<p class="lede"><a href={`/learn/instances/${instanceId}/outcome`}>View outcome</a></p>
		{/if}
	</div>
	{#if !ready}
		<p class="lede">Loading…</p>
	{:else if error}
		<p class="lede error">{error}</p>
	{:else if document}
		<StudentLessonShell
			{document}
			{activeIndex}
			{onActiveIndexChange}
			{attemptsByInteraction}
			{onSubmitAttempt}
		/>
	{/if}
</main>

<style>
	.instance-page {
		min-height: 100vh;
		background: var(--paper);
		color: var(--ink);
	}
	.banner {
		max-width: 1080px;
		margin: 0 auto;
		padding: 20px 18px 0;
	}
	.eyebrow {
		margin: 0 0 6px;
		color: var(--ink-3);
		font: 500 11px 'IBM Plex Mono', monospace;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}
	.lede {
		margin: 0;
		color: var(--ink-2);
		font-size: 13px;
	}
	.lede.error {
		color: var(--amber, #b45309);
		padding: 0 18px;
	}
</style>
