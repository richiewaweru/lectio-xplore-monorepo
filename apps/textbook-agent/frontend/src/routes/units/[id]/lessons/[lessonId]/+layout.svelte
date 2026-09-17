<script lang="ts">
	import { page } from '$app/state';
	import { getUnit, getUnitPath, getPreparedLessonStatus } from '$lib/api/units';
	import type { PathLesson, PreparedLessonStatus, Unit, UnitPath } from '$lib/types/units';
	import { Tabs, Badge } from '$lib/ui';
	import {
		preparationLabel,
		preparationUiState,
		badgeToneForPrep,
		lessonWorkspaceHref
	} from '$lib/curriculum/lessons/lesson-context';
	import { setContext } from 'svelte';

	let { children } = $props();

	const unitId = $derived(page.params.id ?? '');
	const lessonId = $derived(page.params.lessonId ?? '');

	let unit = $state<Unit | null>(null);
	let path = $state<UnitPath | null>(null);
	let lesson = $state<PathLesson | null>(null);
	let preparation = $state<PreparedLessonStatus | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);

	const activeTab = $derived.by(() => {
		const p = page.url.pathname;
		if (p.endsWith('/learn')) return 'learn';
		if (p.endsWith('/print')) return 'print';
		return 'plan';
	});

	const prepState = $derived(preparationUiState(preparation));

	setContext('lessonWorkspace', {
		get unitId() {
			return unitId;
		},
		get lessonId() {
			return lessonId;
		},
		get unit() {
			return unit;
		},
		get path() {
			return path;
		},
		get lesson() {
			return lesson;
		},
		get preparation() {
			return preparation;
		},
		async refreshPreparation() {
			if (!unitId || !lessonId) return;
			try {
				preparation = await getPreparedLessonStatus(unitId, lessonId);
			} catch {
				/* status may 404 before prepare */
			}
		},
		setPreparation(next: PreparedLessonStatus | null) {
			preparation = next;
		}
	});

	async function load() {
		loading = true;
		error = null;
		try {
			unit = await getUnit(unitId);
			path = await getUnitPath(unitId);
			lesson = path.lessons.find((row) => row.id === lessonId) ?? null;
			if (!lesson) {
				error = 'This lesson is not on the current unit path.';
			} else {
				try {
					preparation = await getPreparedLessonStatus(unitId, lessonId);
				} catch {
					preparation = null;
				}
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load lesson.';
		} finally {
			loading = false;
		}
	}

	let lastKey = $state('');
	$effect(() => {
		const key = `${unitId}:${lessonId}`;
		if (!unitId || !lessonId || key === lastKey) return;
		lastKey = key;
		void load();
	});
</script>

{#if loading && !unit}
	<p class="muted">Loading lesson…</p>
{:else if error}
	<p class="err" role="alert">{error}</p>
{:else if unit && lesson}
	<header class="lesson-head">
		<nav class="crumb" aria-label="Breadcrumb">
			<a href="/units">Units</a>
			<span>/</span>
			<a href={`/units/${encodeURIComponent(unitId)}`}>{unit.title}</a>
			<span>/</span>
			<span>{lesson.title}</span>
		</nav>
		<div class="title-row">
			<div>
				<p class="eyebrow">Lesson {lesson.position + 1}</p>
				<h1>{lesson.title}</h1>
				<p class="objective">{lesson.objective}</p>
			</div>
			<Badge tone={badgeToneForPrep(prepState)}>{preparationLabel(prepState)}</Badge>
		</div>
		<Tabs
			active={activeTab}
			tabs={[
				{ id: 'plan', label: 'Plan', href: lessonWorkspaceHref(unitId, lessonId, 'plan') },
				{ id: 'learn', label: 'Learn', href: lessonWorkspaceHref(unitId, lessonId, 'learn') },
				{ id: 'print', label: 'Print', href: lessonWorkspaceHref(unitId, lessonId, 'print') }
			]}
		/>
	</header>
	{@render children()}
{/if}

<style>
	.muted {
		color: var(--ink-2);
	}
	.err {
		color: var(--danger);
	}
	.lesson-head {
		margin-bottom: var(--space-2);
	}
	.crumb {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		align-items: center;
		margin-bottom: var(--space-3);
		color: var(--ink-3);
		font-size: 0.8125rem;
	}
	.crumb a {
		color: var(--ink-2);
		text-decoration: none;
	}
	.crumb a:hover {
		color: var(--accent);
	}
	.title-row {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: var(--space-4);
		margin-bottom: var(--space-4);
	}
	.eyebrow {
		margin: 0 0 0.25rem;
		color: var(--ink-3);
		font-size: 0.75rem;
		font-weight: 600;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}
	h1 {
		margin: 0;
		font-family: var(--font-serif);
		font-size: 1.65rem;
		font-weight: 600;
		letter-spacing: -0.02em;
	}
	.objective {
		margin: 0.4rem 0 0;
		color: var(--ink-2);
		font-size: 0.9375rem;
		max-width: 40rem;
		line-height: 1.5;
	}
</style>
