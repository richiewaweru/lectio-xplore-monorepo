<script lang="ts">
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { learnerFetch } from '$lib/learn/student/api/learner-fetch';
	import { ensureOk } from '$lib/api/errors';
	import InterestCard from '$lib/learn/student/InterestCard.svelte';
	import {
		progressPercent,
		topicAction,
		type OtherLesson,
		type Topic
	} from '$lib/learn/student/topics';


	let ready = $state(false);
	let error = $state<string | null>(null);
	let displayName = $state('');
	let code = $state<string | null>(null);
	let topics = $state<Topic[]>([]);
	let otherLessons = $state<OtherLesson[]>([]);

	const learnerId = $derived(page.params.learnerId);

	onMount(async () => {
		if (!browser || !learnerId) return;
		try {
			const response = await learnerFetch(`/api/v1/learn/learners/${learnerId}/topics`);
			await ensureOk(response);
			const body = await response.json();
			displayName = body.display_name ?? '';
			code = body.code ?? null;
			topics = body.topics ?? [];
			otherLessons = body.other_lessons ?? [];
			ready = true;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load student home';
			ready = true;
		}
	});

	function otherHref(item: OtherLesson): string {
		return item.state === 'done'
			? `/learn/instances/${item.instance_id}/outcome`
			: `/learn/instances/${item.instance_id}`;
	}
	function otherCta(item: OtherLesson): string {
		return item.state === 'done' ? 'View' : item.state === 'current' ? 'Continue' : 'Start';
	}
</script>

<main class="student-home">
	<p class="eyebrow">Student home</p>
	{#if !ready}
		<p class="lede">Loading…</p>
	{:else if error}
		<p class="lede error">{error}</p>
	{:else}
		<header>
			<h1>Hi {displayName}</h1>
			{#if code}
				<p class="code">Your code: <strong>{code}</strong></p>
			{/if}
		</header>

		<section>
			<p class="eyebrow">Your topics</p>
			{#if topics.length}
				<ul class="cards">
					{#each topics as topic (topic.unit_id)}
						{@const action = topicAction(topic)}
						<li class="topic-card">
							<a class="topic-link" href={`/learn/home/${learnerId}/topics/${topic.unit_id}`}>
								<strong>{topic.title}</strong>
								<span class="progress-row">
									<span
										class="bar"
										role="progressbar"
										aria-valuemin="0"
										aria-valuemax="100"
										aria-valuenow={progressPercent(topic)}
										aria-label={`${topic.title} progress`}
									>
										<span class="fill" style={`width: ${progressPercent(topic)}%`}></span>
									</span>
									<span class="count">{topic.lessons_done} of {topic.lessons_total} lessons</span>
								</span>
							</a>
							{#if action.lesson?.instance_id}
								<a class="cta" href={`/learn/instances/${action.lesson.instance_id}`}>
									{action.label} →
								</a>
							{:else if action.kind === 'preparing'}
								<span class="muted">{action.label}</span>
							{:else}
								<a class="cta" href={`/learn/home/${learnerId}/topics/${topic.unit_id}`}>
									{action.label} →
								</a>
							{/if}
						</li>
					{/each}
				</ul>
			{:else}
				<p class="empty">No topics yet.</p>
			{/if}
		</section>

		{#if otherLessons.length}
			<section class="other">
				<p class="eyebrow">Other lessons</p>
				<ul class="cards">
					{#each otherLessons as item (item.instance_id)}
						<li>
							<a class="plain" href={otherHref(item)}>
								<strong>{item.title || 'Lesson'}</strong>
								<span class="cta">{otherCta(item)} →</span>
							</a>
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		<InterestCard source="home" />
	{/if}
</main>

<style>
	.student-home {
		max-width: 720px;
		margin: 0 auto;
		padding: 28px 18px 48px;
		color: var(--ink);
		background: var(--paper);
		min-height: 100vh;
		display: grid;
		align-content: start;
		gap: 22px;
		box-sizing: border-box;
	}
	.eyebrow {
		margin: 0 0 6px;
		color: var(--ink-3);
		font: 500 11px 'IBM Plex Mono', monospace;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}
	h1 {
		margin: 0;
		font: 500 34px/1.1 Fraunces, Georgia, serif;
		overflow-wrap: anywhere;
	}
	.lede {
		color: var(--ink-2);
		font-size: 14px;
		margin: 0;
	}
	.lede.error {
		color: var(--amber, #b45309);
	}
	.code {
		margin: 8px 0 0;
		color: var(--ink-2);
		font-size: 14px;
	}
	.code strong {
		font: 500 14px 'IBM Plex Mono', monospace;
		letter-spacing: 0.06em;
		color: var(--ink);
		overflow-wrap: anywhere;
	}
	.cards {
		list-style: none;
		margin: 8px 0 0;
		padding: 0;
		display: grid;
		gap: 10px;
	}
	.topic-card,
	.plain {
		display: grid;
		gap: 10px;
		border: 1px solid var(--rule);
		border-radius: 12px;
		background: var(--surface);
		padding: 14px;
		color: inherit;
	}
	.plain {
		text-decoration: none;
		gap: 4px;
	}
	.topic-link {
		display: grid;
		gap: 10px;
		text-decoration: none;
		color: inherit;
	}
	.topic-link strong {
		font: 500 20px/1.2 Fraunces, Georgia, serif;
		overflow-wrap: anywhere;
	}
	.progress-row {
		display: flex;
		align-items: center;
		gap: 12px;
	}
	.bar {
		flex: 1;
		min-width: 0;
		height: 6px;
		border-radius: 999px;
		background: var(--rule);
		overflow: hidden;
	}
	.fill {
		display: block;
		height: 100%;
		background: var(--accent);
	}
	.count {
		color: var(--ink-3);
		font: 500 11px 'IBM Plex Mono', monospace;
		white-space: nowrap;
	}
	.cta {
		color: var(--accent);
		font-size: 0.8125rem;
		font-weight: 550;
		text-decoration: none;
		overflow-wrap: anywhere;
	}
	.muted,
	.empty {
		color: var(--ink-3);
		font-size: 14px;
	}
	@media (max-width: 720px) {
		h1 {
			font-size: 28px;
		}
	}
</style>
