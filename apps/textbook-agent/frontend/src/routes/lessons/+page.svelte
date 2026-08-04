<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { fromStore } from 'svelte/store';
	import { goto } from '$app/navigation';
	import { isApiError } from '$lib/api/errors';
	import { fetchV3Document, getChunkedPlanStatus, getV3Generations } from '$lib/api/v3';
	import {
		deleteBuilderLesson,
		getBuilderLesson,
		listBuilderLessons,
		type BuilderLessonRecord,
		type BuilderLessonSummary
	} from '$lib/builder/api/lesson-crud';
	import NewLessonSplitButton from '$lib/components/workspace/NewLessonSplitButton.svelte';
	import { createGenerationPoller } from '$lib/generation/generation-poller';
	import { authUser, logout } from '$lib/stores/auth';
	import type { V3PackDocument } from '$lib/studio/v3-pack-to-lectio-document';
	import type { V3GenerationHistoryItem } from '$lib/types/v3';
	import { deriveLessonRows, type LessonRow, type LessonState } from '$lib/workspace/lesson-state';
	import type { LessonDocument } from 'lectio';

	let loading = $state(true);
	let errorMessage = $state<string | null>(null);
	let rows = $state<LessonRow[]>([]);
	let lessons = $state<BuilderLessonSummary[]>([]);
	let generations = $state<V3GenerationHistoryItem[]>([]);
	let generationDocumentsById = $state<Record<string, V3PackDocument | undefined>>({});
	let lessonDocumentsById = $state<Record<string, LessonDocument | undefined>>({});
	let documentVersionsByGenerationId = $state<Record<string, string | null | undefined>>({});
	let deletingLessonId = $state<string | null>(null);
	let deleteError = $state<string | null>(null);
	const user = fromStore(authUser);

	const writing = $derived(rows.filter((row) => row.state === 'writing'));
	const attention = $derived(rows.filter((row) => row.state === 'attention'));
	const ready = $derived(rows.filter((row) => row.state === 'ready'));
	const drafts = $derived(rows.filter((row) => row.state === 'draft'));
	const greeting = $derived(new Date().getHours() < 12 ? 'Good morning' : new Date().getHours() < 18 ? 'Good afternoon' : 'Good evening');
	const firstName = $derived(user.current?.name?.trim().split(/\s+/)[0] ?? '');
	const workspacePoller = createGenerationPoller(pollWritingRows);

	function dismissedIssueIds(): Record<string, string[]> {
		if (typeof localStorage === 'undefined') return {};
		return Object.fromEntries(
			lessons.map((lesson) => {
				try {
					const parsed = JSON.parse(
						localStorage.getItem(`lectio:dismissed-doc-issues:${lesson.id}`) ?? '[]'
					);
					return [
						lesson.id,
						Array.isArray(parsed)
							? parsed.filter((value): value is string => typeof value === 'string')
							: []
					];
				} catch {
					return [lesson.id, []];
				}
			})
		);
	}

	function rebuildRows(): void {
		rows = deriveLessonRows({
			lessons,
			generations,
			generationDocumentsById,
			lessonDocumentsById,
			dismissedIssueIdsByLessonId: dismissedIssueIds()
		});
	}

	async function pollWritingRows(): Promise<void> {
		const writingGenerationIds = rows
			.filter((row) => row.state === 'writing')
			.map((row) => lessons.find((lesson) => lesson.id === row.id)?.source_generation_id)
			.filter((id): id is string => Boolean(id));
		if (writingGenerationIds.length === 0) {
			workspacePoller.stop();
			return;
		}

		const statuses = await Promise.all(
			writingGenerationIds.map(async (generationId) => [
				generationId,
				await getChunkedPlanStatus(generationId)
			] as const)
		);
		for (const [generationId, status] of statuses) {
			const terminal =
				status.stage === 'complete' ||
				status.stage === 'assembly_blocked' ||
				status.stage === 'stage2_error' ||
				status.next_action === 'done';
			const versionChanged =
				typeof status.doc_version === 'string' &&
				status.doc_version !== documentVersionsByGenerationId[generationId];
			if (versionChanged || terminal) {
				try {
					generationDocumentsById = {
						...generationDocumentsById,
						[generationId]: (await fetchV3Document(generationId)) as V3PackDocument
					};
				} catch {
					// Keep the last known snapshot and retry while the row remains active.
				}
			}
			documentVersionsByGenerationId = {
				...documentVersionsByGenerationId,
				[generationId]: status.doc_version
			};
			if (status.stage === 'assembly_blocked' || status.stage === 'stage2_error') {
				generations = generations.map((generation) =>
					generation.id === generationId
						? { ...generation, status: 'failed_finalisation' }
						: generation
				);
			}
		}
		rebuildRows();
		if (!rows.some((row) => row.state === 'writing')) workspacePoller.stop();
	}

	function relativeTime(value: string): string {
		const timestamp = new Date(value).getTime();
		if (!Number.isFinite(timestamp)) return value;
		const minutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60_000));
		if (minutes < 1) return 'just now';
		if (minutes < 60) return `${minutes} min ago`;
		const hours = Math.floor(minutes / 60);
		if (hours < 24) return `${hours} hr${hours === 1 ? '' : 's'} ago`;
		const days = Math.floor(hours / 24);
		if (days === 1) return 'yesterday';
		if (days < 7) return `${days} days ago`;
		return new Date(value).toLocaleDateString();
	}

	function rowMeta(row: LessonRow): string {
		if (row.awaitingReview) return 'Concepts ready for review';
		if (row.state === 'writing') {
			return row.sectionsDone !== null && row.sectionsTotal
				? `Writing section ${Math.min(row.sectionsDone + 1, row.sectionsTotal)} of ${row.sectionsTotal}`
				: 'Writing lesson';
		}
		if (row.state === 'attention' && row.flagCount === 0) return 'Generation failed — try again';
		if (row.state === 'ready') {
			return row.sectionsTotal ? `${row.sectionsTotal} sections` : 'Ready';
		}
		return row.sectionsTotal ? 'Plan approved, not generated' : 'Not started';
	}

	function groupTitle(state: LessonState): string {
		if (state === 'writing') return 'Writing now';
		if (state === 'attention') return 'Needs you';
		if (state === 'ready') return 'Ready to print';
		return 'Drafts';
	}

	async function deleteLesson(row: LessonRow): Promise<void> {
		if (!confirm(`Delete “${row.title}”? This cannot be undone.`)) return;
		deletingLessonId = row.id;
		deleteError = null;
		try {
			await deleteBuilderLesson(row.id);
			lessons = lessons.filter((lesson) => lesson.id !== row.id);
			const { [row.id]: _removedDocument, ...remainingDocuments } = lessonDocumentsById;
			lessonDocumentsById = remainingDocuments;
			rebuildRows();
		} catch (error) {
			deleteError = error instanceof Error ? error.message : 'Failed to delete lesson.';
		} finally {
			deletingLessonId = null;
		}
	}

	async function loadWorkspace(): Promise<void> {
		try {
			const [loadedLessons, loadedGenerations] = await Promise.all([
				listBuilderLessons(),
				getV3Generations()
			]);
			lessons = loadedLessons;
			generations = loadedGenerations;
			const generationIds = new Set(
				lessons
					.map((lesson) => lesson.source_generation_id)
					.filter((id): id is string => Boolean(id))
			);
			const [lessonRecords, generationEntries] = await Promise.all([
				Promise.all(
					lessons.map(async (lesson) => {
						try {
							return await getBuilderLesson(lesson.id);
						} catch (error) {
							if (isApiError(error) && error.status === 401) throw error;
							return undefined;
						}
					})
				),
				Promise.all(
					[...generationIds].map(async (generationId) => {
						try {
							return [generationId, (await fetchV3Document(generationId)) as V3PackDocument] as const;
						} catch (error) {
							if (isApiError(error) && error.status === 401) throw error;
							return [generationId, undefined] as const;
						}
					})
				)
			]);
			lessonDocumentsById = Object.fromEntries(
				lessonRecords
					.filter((record): record is BuilderLessonRecord => Boolean(record))
					.map((record) => [record.id, record.document])
			);
			generationDocumentsById = Object.fromEntries(generationEntries);
			rebuildRows();
			if (rows.some((row) => row.state === 'writing')) workspacePoller.start();
		} catch (error) {
			if (isApiError(error) && error.status === 401) {
				logout();
				await goto('/login', { replaceState: true });
				return;
			}
			errorMessage = error instanceof Error ? error.message : 'Failed to load lessons.';
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		void loadWorkspace();
	});

	onDestroy(() => workspacePoller.stop());
</script>

<svelte:head>
	<title>Lessons · Lectio</title>
</svelte:head>

<div class="workspace-page">
		<header class="page-head">
			<div>
				<p class="date-line">
					{new Intl.DateTimeFormat('en-US', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date())}
				</p>
				<h1>{greeting}{firstName ? `, ${firstName}` : ''}</h1>
			</div>
			{#if loading || errorMessage || rows.length > 0}
				<NewLessonSplitButton />
			{/if}
		</header>

		{#if loading}
			<p class="status-copy" role="status">Loading lessons…</p>
		{:else if errorMessage}
			<p class="error-copy" role="alert">{errorMessage}</p>
		{:else if rows.length === 0}
			<section class="empty">
				<p>No lessons yet. Start with the class and topic you want to teach.</p>
				<NewLessonSplitButton />
			</section>
		{:else}
			{#if deleteError}<p class="error-copy delete-error" role="alert">{deleteError}</p>{/if}
			{#each [
				{ state: 'writing' as const, rows: writing },
				{ state: 'attention' as const, rows: attention },
				{ state: 'ready' as const, rows: ready }
			] as group}
				{#if group.rows.length > 0}
					<section class="group" data-group={group.state}>
						<div class="group-head">
							<span class="group-title">{groupTitle(group.state)}</span>
							<hr />
							{#if group.state !== 'writing'}<span class="count">{group.rows.length}</span>{/if}
						</div>
						<div class="row-list">
							{#each group.rows as row (row.id)}
								<article class:live={row.state === 'writing'} class:attention={row.state === 'attention'} class="lesson-row">
									<div class="row-copy">
										<a class="title" href={row.href}>
											{#if row.state === 'writing'}<span class="pulse" aria-hidden="true"></span>{/if}
											<span>{row.title}</span>
											{#if row.classLabel}<span class="klass">· {row.classLabel}</span>{/if}
										</a>
										<p class="meta">
											{#if row.state === 'attention' && row.flagCount > 0}
												<span class="flag">{row.flagCount} {row.flagCount === 1 ? 'item' : 'items'} to check</span>
												<span class="dot">·</span>
											{/if}
											<span>{rowMeta(row)}</span>
											<span class="dot">·</span>
											<span>{relativeTime(row.updatedAt)}</span>
										</p>
									</div>
									{#if row.state === 'writing'}
										<div class="live-side" aria-label={`${row.sectionsDone ?? 0} of ${row.sectionsTotal ?? 0} sections ready`}>
											<div class="track">
												<span
													class="fill"
													style={`width:${row.sectionsTotal ? Math.round(((row.sectionsDone ?? 0) / row.sectionsTotal) * 100) : 0}%`}
												></span>
											</div>
											<span class="frac">{row.sectionsDone ?? 0} / {row.sectionsTotal ?? '—'}</span>
										</div>
									{:else}
										<div class="actions">
											{#if row.state === 'attention'}
												<a class="action solid" href={row.href}>{row.awaitingReview ? 'Review concepts' : 'Review'}</a>
											{:else}
												<a class="action" href={row.href}>Edit</a>
												<a class="action solid" href={`/builder/print/${row.id}`}>Print</a>
											{/if}
											<details class="row-menu">
												<summary class="action" aria-label={`More actions for ${row.title}`}>•••</summary>
												<div class="menu-popover">
													<button
														type="button"
														disabled={deletingLessonId === row.id}
														onclick={() => deleteLesson(row)}
													>
														{deletingLessonId === row.id ? 'Deleting…' : 'Delete lesson'}
													</button>
												</div>
											</details>
										</div>
									{/if}
								</article>
							{/each}
						</div>
					</section>
				{/if}
			{/each}

			{#if drafts.length > 0}
				<section class="group" data-group="draft">
					<details class="drafts">
						<summary>
							<div class="group-head">
								<span class="group-title"><span class="chevron" aria-hidden="true">▸</span> Drafts</span>
								<hr />
								<span class="count">{drafts.length}</span>
							</div>
						</summary>
						<div class="row-list">
							{#each drafts as row (row.id)}
								<article class="lesson-row">
									<div class="row-copy">
										<a class="title" href={row.href}>
											<span>{row.title}</span>
											{#if row.classLabel}<span class="klass">· {row.classLabel}</span>{/if}
										</a>
										<p class="meta">
											<span>{rowMeta(row)}</span><span class="dot">·</span><span>{relativeTime(row.updatedAt)}</span>
										</p>
									</div>
									<div class="actions">
										<button
											class="action danger"
											type="button"
											disabled={deletingLessonId === row.id}
											onclick={() => deleteLesson(row)}
										>
											{deletingLessonId === row.id ? 'Deleting…' : 'Delete'}
										</button>
										<a class="action solid" href={row.href}>Continue</a>
									</div>
								</article>
							{/each}
						</div>
					</details>
				</section>
			{/if}
		{/if}
</div>

<style>
	.workspace-page {
		box-sizing: border-box;
		min-height: calc(100vh - 58px);
		background: var(--paper);
		padding: 54px 28px 80px;
		color: var(--ink);
	}

	.workspace-page :global(*) {
		box-sizing: border-box;
	}

	.page-head,
	.group,
	.empty,
	.status-copy,
	.error-copy {
		max-width: 860px;
		margin-right: auto;
		margin-left: auto;
	}

	.page-head {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: 24px;
		margin-bottom: 50px;
	}

	.date-line {
		margin: 0 0 7px;
		color: var(--ink-3);
		font: 500 11px 'IBM Plex Mono', monospace;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	h1 {
		margin: 0;
		font: 500 36px/1.1 Fraunces, Georgia, serif;
		letter-spacing: -0.03em;
	}

	.group {
		margin-bottom: 36px;
	}

	.group-head {
		display: flex;
		align-items: center;
		gap: 12px;
		margin-bottom: 6px;
	}

	.group-head hr {
		flex: 1;
		height: 0;
		margin: 0;
		border: 0;
		border-top: 1px solid var(--rule);
	}

	.group-title,
	.count {
		color: var(--ink-3);
		font: 500 11px 'IBM Plex Mono', monospace;
	}

	.group-title {
		letter-spacing: 0.11em;
		text-transform: uppercase;
	}

	.row-list {
		display: grid;
	}

	.lesson-row {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		align-items: center;
		gap: 20px;
		border-bottom: 1px solid var(--rule);
		border-radius: 8px;
		padding: 15px 16px;
		transition: background 0.12s;
	}

	.lesson-row:last-child {
		border-bottom-color: transparent;
	}

	.lesson-row:hover {
		background: var(--surface);
	}

	.lesson-row.live {
		border: 1px solid var(--rule);
		background: var(--surface);
		box-shadow: 0 1px 2px rgba(22, 33, 28, 0.04);
	}

	.title {
		display: flex;
		align-items: center;
		gap: 9px;
		min-width: 0;
		margin: 0 0 3px;
		color: var(--ink);
		font-weight: 500;
		letter-spacing: -0.005em;
		text-decoration: none;
	}

	.klass {
		color: var(--ink-3);
		font-weight: 400;
	}

	.meta {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 7px;
		margin: 0;
		color: var(--ink-2);
		font-size: 13px;
	}

	.dot {
		color: var(--rule);
	}

	.actions {
		display: flex;
		gap: 4px;
		opacity: 0;
		transition: opacity 0.12s;
	}

	.lesson-row:hover .actions,
	.lesson-row:focus-within .actions,
	.lesson-row.attention .actions {
		opacity: 1;
	}

	.action {
		border: 1px solid transparent;
		border-radius: 6px;
		color: var(--ink-2);
		font-size: 13px;
		font-weight: 500;
		padding: 6px 12px;
		text-decoration: none;
	}

	button.action {
		background: transparent;
		cursor: pointer;
		font-family: inherit;
	}

	button.action:disabled {
		cursor: progress;
		opacity: 0.6;
	}

	.action.danger:hover,
	.action.danger:focus-visible {
		background: #f8e9e5;
		color: #873f30;
	}

	.action:hover,
	.action:focus-visible {
		background: var(--accent-soft);
		color: var(--accent);
	}

	.action.solid {
		border-color: var(--rule);
		background: var(--surface);
		color: var(--ink);
	}

	.title:focus-visible,
	.action:focus-visible,
	summary:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 3px;
	}

	.pulse {
		flex: none;
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--accent);
		animation: pulse 1.8s ease-in-out infinite;
	}

	.live-side {
		text-align: right;
	}

	.track {
		width: 118px;
		height: 3px;
		margin-bottom: 7px;
		overflow: hidden;
		border-radius: 2px;
		background: var(--rule);
	}

	.fill {
		display: block;
		height: 100%;
		border-radius: 2px;
		background: var(--accent);
		transition: width 0.2s ease;
	}

	.frac {
		color: var(--ink-2);
		font: 500 12px 'IBM Plex Mono', monospace;
	}

	.flag {
		display: inline-flex;
		align-items: center;
		border-radius: 999px;
		background: var(--amber-soft);
		color: var(--amber);
		font: 500 12px Inter, sans-serif;
		padding: 3px 9px;
	}

	.row-menu {
		position: relative;
	}

	.row-menu summary {
		cursor: pointer;
		list-style: none;
	}

	.row-menu summary::-webkit-details-marker {
		display: none;
	}

	.menu-popover {
		position: absolute;
		top: calc(100% + 6px);
		right: 0;
		z-index: 5;
		min-width: 132px;
		border: 1px solid var(--rule);
		border-radius: 8px;
		background: var(--surface);
		box-shadow: 0 8px 24px rgba(22, 33, 28, 0.12);
		padding: 5px;
	}

	.menu-popover button {
		width: 100%;
		border: 0;
		border-radius: 5px;
		background: transparent;
		color: #873f30;
		cursor: pointer;
		font: 500 13px Inter, sans-serif;
		padding: 8px;
		text-align: left;
	}

	.menu-popover button:hover,
	.menu-popover button:focus-visible {
		background: #f8e9e5;
		outline: none;
	}

	.delete-error {
		margin-bottom: 20px;
	}

	.drafts summary {
		cursor: pointer;
		list-style: none;
	}

	.drafts summary::-webkit-details-marker {
		display: none;
	}

	.chevron {
		display: inline-block;
		font-size: 11px;
		transition: transform 0.15s;
	}

	.drafts[open] .chevron {
		transform: rotate(90deg);
	}

	.empty {
		border: 1px dashed var(--rule);
		border-radius: 8px;
		padding: 44px 28px;
		text-align: center;
	}

	.empty p {
		margin: 0 0 18px;
		color: var(--ink-2);
		font-size: 14px;
	}

	.error-copy {
		color: #873f30;
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.25;
		}
	}

	@media (max-width: 640px) {
		.workspace-page {
			padding: 36px 18px 60px;
		}

		.page-head {
			align-items: stretch;
			flex-direction: column;
			margin-bottom: 38px;
		}

		h1 {
			font-size: 32px;
		}

		.lesson-row {
			grid-template-columns: minmax(0, 1fr);
			gap: 12px;
		}

		.actions {
			opacity: 1;
		}

		.live-side {
			text-align: left;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.workspace-page :global(*) {
			animation: none !important;
			transition: none !important;
		}
	}
</style>
