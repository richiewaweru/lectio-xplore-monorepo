<script lang="ts">
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { learnerFetch } from '$lib/learn/student/api/learner-fetch';
	import { ensureOk } from '$lib/api/errors';
	import {
		currentLessonId,
		isOpenable,
		progressPercent,
		type Topic,
		type TopicLesson
	} from '$lib/learn/student/topics';

	let ready = $state(false);
	let error = $state<string | null>(null);
	let topic = $state<Topic | null>(null);

	const learnerId = $derived(page.params.learnerId);
	const unitId = $derived(page.params.unitId);

	onMount(async () => {
		if (!browser || !learnerId || !unitId) return;
		try {
			const response = await learnerFetch(`/api/v1/learn/learners/${learnerId}/topics`);
			await ensureOk(response);
			const body = await response.json();
			topic = (body.topics ?? []).find((t: Topic) => t.unit_id === unitId) ?? null;
			if (!topic) error = 'This topic was not found.';
			ready = true;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load topic';
			ready = true;
		}
	});

	const hereId = $derived(topic ? currentLessonId(topic) : null);
	const lessons = $derived(
		topic ? [...topic.lessons].sort((a, b) => a.position - b.position) : []
	);

	function marker(lesson: TopicLesson): string {
		if (lesson.state === 'done') return '✓';
		if (lesson.state === 'current') return '▸';
		if (lesson.state === 'pending' || !lesson.instance_id) return '~';
		return '';
	}
	function statusText(lesson: TopicLesson): string {
		if (lesson.state === 'done') return 'Done';
		if (lesson.state === 'pending' || !lesson.instance_id) return 'Being prepared';
		if (lesson.state === 'current') return 'Continue →';
		return hereId === lesson.path_lesson_id ? 'Up next' : 'Start →';
	}
</script>

<main class="topic-page">
	<a class="back" href={`/learn/home/${learnerId}`}>← Home</a>
	{#if !ready}
		<p class="lede">Loading…</p>
	{:else if error || !topic}
		<p class="lede error">{error ?? 'This topic was not found.'}</p>
	{:else}
		<header>
			<p class="eyebrow">{topic.title}</p>
			{#if topic.summary}
				<h1>{topic.summary}</h1>
			{:else}
				<h1>{topic.title}</h1>
			{/if}
			<div class="progress-row">
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
			</div>
		</header>

		<ol class="roadmap">
			{#each lessons as lesson (lesson.path_lesson_id)}
				{@const openable = isOpenable(lesson)}
				<li class={`step ${lesson.state}`} class:here={hereId === lesson.path_lesson_id}>
					<span class="node" aria-hidden="true">{marker(lesson)}</span>
					<div class="body">
						{#if openable}
							<a class="lesson-title" href={`/learn/instances/${lesson.instance_id}`}>
								<span class="num">{lesson.position}</span>
								{lesson.title}
							</a>
						{:else}
							<p class="lesson-title muted">
								<span class="num">{lesson.position}</span>
								{lesson.title}
							</p>
						{/if}
						<p class="status">
							{statusText(lesson)}
							{#if hereId === lesson.path_lesson_id && lesson.state === 'current'}
								<span class="here-tag">you are here</span>
							{/if}
						</p>
						{#if lesson.best_after_position && lesson.state !== 'done'}
							<p class="best">Best after Lesson {lesson.best_after_position}</p>
						{/if}
					</div>
				</li>
			{/each}
		</ol>
	{/if}
</main>

<style>
	.topic-page {
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
	.back {
		color: var(--ink-2);
		font-size: 14px;
		text-decoration: none;
	}
	.eyebrow {
		margin: 0 0 6px;
		color: var(--ink-3);
		font: 500 11px 'IBM Plex Mono', monospace;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		overflow-wrap: anywhere;
	}
	h1 {
		margin: 0 0 14px;
		font: 500 28px/1.2 Fraunces, Georgia, serif;
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
	.roadmap {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
	}
	.step {
		display: grid;
		grid-template-columns: 28px minmax(0, 1fr);
		gap: 14px;
		position: relative;
		padding-bottom: 20px;
	}
	.step:not(:last-child)::before {
		content: '';
		position: absolute;
		left: 13px;
		top: 28px;
		bottom: 0;
		width: 1px;
		background: var(--rule);
	}
	.node {
		width: 26px;
		height: 26px;
		border-radius: 999px;
		border: 1px solid var(--rule);
		background: var(--paper);
		display: grid;
		place-items: center;
		font: 500 12px 'IBM Plex Mono', monospace;
		color: var(--ink-3);
	}
	.done .node {
		background: var(--accent);
		border-color: var(--accent);
		color: var(--paper);
	}
	.current .node {
		border-color: var(--accent);
		color: var(--accent);
	}
	.pending .node {
		border-style: dashed;
	}
	.body {
		min-width: 0;
		display: grid;
		gap: 4px;
	}
	.lesson-title {
		margin: 0;
		font: 500 17px/1.3 Fraunces, Georgia, serif;
		color: inherit;
		text-decoration: none;
		overflow-wrap: anywhere;
	}
	.lesson-title.muted {
		color: var(--ink-3);
	}
	.num {
		font: 500 11px 'IBM Plex Mono', monospace;
		color: var(--ink-3);
		margin-right: 6px;
	}
	.status {
		margin: 0;
		font-size: 13px;
		color: var(--ink-2);
	}
	.current .status,
	.ready .status {
		color: var(--accent);
		font-weight: 550;
	}
	.here-tag {
		margin-left: 8px;
		color: var(--ink-3);
		font: 500 11px 'IBM Plex Mono', monospace;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}
	.best {
		margin: 0;
		font-size: 12px;
		color: var(--ink-3);
	}
</style>
