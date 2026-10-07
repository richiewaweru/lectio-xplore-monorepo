<script lang="ts">
	import { dismissLessonIssue, restoreLessonIssue } from '$lib/api/units';
	import type { LessonIssue, LessonIssueCounts } from '$lib/types/units';
	import { sectionHref } from './section-focus';

	interface Props {
		issues?: LessonIssue[];
		/** Counts from the backend; derived from `issues` when omitted. */
		counts?: LessonIssueCounts | null;
		onRetry?: () => void | Promise<void>;
		allowRetry?: boolean;
		/** Needed for "Mark as fine" / Restore. */
		unitId?: string;
		lessonId?: string;
		path?: 'learn' | 'print';
		/** Editor for this output, e.g. `/builder/<id>` or `/studio/print/<id>`; `null` when it is not built. */
		editBaseHref?: string | null;
	}

	let {
		issues = [],
		counts = null,
		onRetry,
		allowRetry = false,
		unitId,
		lessonId,
		path,
		editBaseHref = null
	}: Props = $props();

	let items = $state<LessonIssue[]>([]);
	let serverCounts = $state<LessonIssueCounts | null>(null);
	let busyId = $state<string | null>(null);
	let actionError = $state<string | null>(null);

	$effect(() => {
		items = issues;
		serverCounts = counts;
	});

	const blocking = $derived(items.filter((issue) => issue.group === 'blocking' && !issue.dismissed));
	const needsLook = $derived(items.filter((issue) => issue.group === 'needs_look' && !issue.dismissed));
	const info = $derived(items.filter((issue) => issue.group === 'info' && !issue.dismissed));
	const dismissed = $derived(items.filter((issue) => issue.dismissed));
	const attentionCount = $derived(serverCounts?.attention ?? blocking.length + needsLook.length);
	const canDismiss = $derived(Boolean(unitId && lessonId && path));
	const nothingToShow = $derived(
		blocking.length === 0 && needsLook.length === 0 && dismissed.length === 0
	);

	function heading(issue: LessonIssue): string {
		if (issue.section_title) return issue.section_title;
		return issue.section_id ? 'A section of this lesson' : 'Whole lesson';
	}

	async function change(issue: LessonIssue, action: 'dismiss' | 'restore'): Promise<void> {
		if (!unitId || !lessonId || !path) return;
		busyId = issue.id;
		actionError = null;
		try {
			const response =
				action === 'dismiss'
					? await dismissLessonIssue(unitId, lessonId, path, issue.id)
					: await restoreLessonIssue(unitId, lessonId, path, issue.id);
			items = response.issues;
			serverCounts = response.counts;
		} catch (err) {
			actionError = err instanceof Error ? err.message : 'Could not update this item.';
		} finally {
			busyId = null;
		}
	}
</script>

{#snippet moreInfo(issue: LessonIssue)}
	<details class="details">
		<summary>Details</summary>
		<p>{issue.category} · {issue.code}</p>
		{#if issue.details}<p>{issue.details}</p>{/if}
	</details>
{/snippet}

{#snippet card(issue: LessonIssue)}
	{@const href = issue.group === 'needs_look' ? sectionHref(editBaseHref, issue.section_id) : null}
	<li class="item {issue.group}" data-testid="issue-item" data-group={issue.group}>
		<p class="where">{heading(issue)}</p>
		<p class="what">{issue.message}</p>
		{#if issue.suggestion && issue.group !== 'info'}<p class="suggestion">{issue.suggestion}</p>{/if}
		<div class="actions">
			{#if issue.group === 'blocking' && allowRetry && issue.repairable && onRetry}
				<button type="button" onclick={() => void onRetry?.()}>Retry</button>
			{/if}
			{#if href && !issue.dismissed}
				<a class="link" data-testid="go-to-section" {href}>Go to section</a>
			{/if}
			{#if issue.dismissible && canDismiss}
				{#if issue.dismissed}
					<button type="button" class="secondary" disabled={busyId === issue.id} onclick={() => void change(issue, 'restore')}>Restore</button>
				{:else}
					<button type="button" class="secondary" disabled={busyId === issue.id} onclick={() => void change(issue, 'dismiss')}>Mark as fine</button>
				{/if}
			{/if}
		</div>
		{@render moreInfo(issue)}
	</li>
{/snippet}

{#if nothingToShow}
	<section class="empty" data-testid="no-issues">
		<p class="success">✓ No issues detected</p>
		<p>Nothing in this lesson needs your attention.</p>
	</section>
{/if}

{#if info.length > 0 && nothingToShow}
	<details class="group info-group" data-testid="info-group">
		<summary>Notes ({info.length})</summary>
		<ul>{#each info as issue (issue.id)}{@render card(issue)}{/each}</ul>
	</details>
{/if}

{#if !nothingToShow}
	<section class="issues" data-testid="lesson-issues">
		<header>
			<h2>Issues</h2>
			<span data-testid="attention-count">{attentionCount === 1 ? '1 needs attention' : `${attentionCount} need attention`}</span>
		</header>
		{#if actionError}<p class="error" role="alert">{actionError}</p>{/if}

		{#if blocking.length > 0}
			<div class="group" data-testid="group-blocking">
				<h3>This lesson didn't finish</h3>
				<ul>{#each blocking as issue (issue.id)}{@render card(issue)}{/each}</ul>
			</div>
		{/if}

		{#if needsLook.length > 0}
			<div class="group" data-testid="group-needs-look">
				<h3>Needs a look</h3>
				<ul>{#each needsLook as issue (issue.id)}{@render card(issue)}{/each}</ul>
			</div>
		{/if}

		{#if info.length > 0}
			<details class="group info-group" data-testid="info-group">
				<summary>Notes ({info.length})</summary>
				<ul>{#each info as issue (issue.id)}{@render card(issue)}{/each}</ul>
			</details>
		{/if}

		{#if dismissed.length > 0}
			<details class="group dismissed-group" data-testid="group-dismissed">
				<summary>Marked as fine ({dismissed.length})</summary>
				<ul>{#each dismissed as issue (issue.id)}{@render card(issue)}{/each}</ul>
			</details>
		{/if}
	</section>
{/if}

<style>
	.empty, .issues { border: 1px solid var(--rule); border-radius: var(--radius-lg); background: var(--surface); padding: var(--space-4); }
	.empty p, .issues p { margin: 0; color: var(--ink-2); line-height: 1.5; }
	.success { color: var(--success) !important; font-weight: 600; }
	header { display: flex; justify-content: space-between; gap: var(--space-3); align-items: baseline; }
	h2 { margin: 0; font: 600 1.15rem var(--font-serif); }
	h3 { margin: var(--space-4) 0 0; font-size: 0.8125rem; font-weight: 700; letter-spacing: 0.02em; text-transform: uppercase; color: var(--ink-2); }
	header span { color: var(--ink-2); font-size: 0.8125rem; }
	ul { display: grid; gap: var(--space-2); list-style: none; margin: var(--space-2) 0 0; padding: 0; }
	.item { border-left: 3px solid var(--warning, #b45309); border-radius: var(--radius-sm); background: color-mix(in srgb, var(--warning, #b45309) 6%, transparent); padding: var(--space-3); }
	.item.blocking { border-left-color: var(--danger); background: color-mix(in srgb, var(--danger) 5%, transparent); }
	.item.info { border-left-color: var(--ink-3); background: transparent; opacity: 0.85; }
	.where { font-size: 0.75rem; font-weight: 700; color: var(--ink-3) !important; text-transform: uppercase; letter-spacing: 0.03em; }
	.what { color: var(--ink-1, inherit) !important; font-weight: 600; margin-top: 2px !important; }
	.suggestion { margin-top: var(--space-1, 4px) !important; }
	.actions { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; margin-top: var(--space-2); }
	.actions:empty { display: none; }
	button { border: 0; border-radius: var(--radius-sm); background: var(--accent); color: white; padding: 0.4rem 0.7rem; cursor: pointer; }
	button.secondary { background: transparent; color: var(--ink-2); border: 1px solid var(--rule); }
	button:disabled { opacity: 0.6; cursor: default; }
	.link { color: var(--accent); font-size: 0.875rem; font-weight: 600; text-decoration: underline; }
	.group { margin-top: var(--space-3); }
	summary { cursor: pointer; color: var(--ink-2); font-size: 0.8125rem; font-weight: 600; }
	.details { margin-top: var(--space-2); }
	.details p { font-size: 0.75rem; color: var(--ink-3) !important; word-break: break-word; }
	.error { color: var(--danger) !important; margin-top: var(--space-2) !important; }
</style>
