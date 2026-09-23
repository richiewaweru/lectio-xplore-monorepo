<script lang="ts">
	import type { LessonIssue } from '$lib/types/units';

	interface Props {
		issues?: LessonIssue[];
		onRetry?: () => void | Promise<void>;
		allowRetry?: boolean;
	}

	let { issues = [], onRetry, allowRetry = false }: Props = $props();
	const attentionCount = $derived(issues.filter((issue) => issue.severity !== 'info').length);
</script>

{#if issues.length === 0}
	<section class="empty" data-testid="no-issues">
		<p class="success">✓ No issues detected</p>
		<p>The current artifact has no known blocking or advisory issues.</p>
	</section>
{:else}
	<section class="issues" data-testid="lesson-issues">
		<header><h2>Issues</h2><span>{attentionCount} need attention</span></header>
		<ul>
			{#each issues as issue (issue.id)}
				<li class:info={issue.severity === 'info'}>
					<div class="issue-head"><span class="severity">{issue.severity}</span><strong>{issue.message}</strong></div>
					<p>{issue.category} · {issue.code}{#if issue.target_id} · Target: {issue.target_id}{/if}</p>
					{#if allowRetry && issue.repairable && onRetry}<button type="button" onclick={() => void onRetry?.()}>Retry</button>{/if}
				</li>
			{/each}
		</ul>
	</section>
{/if}

<style>
	.empty, .issues { border: 1px solid var(--rule); border-radius: var(--radius-lg); background: var(--surface); padding: var(--space-4); }
	.empty p, .issues p { margin: 0; color: var(--ink-2); line-height: 1.5; }
	.success { color: var(--success) !important; font-weight: 600; }
	header { display: flex; justify-content: space-between; gap: var(--space-3); align-items: baseline; }
	h2 { margin: 0; font: 600 1.15rem var(--font-serif); }
	header span { color: var(--ink-2); font-size: 0.8125rem; }
	ul { display: grid; gap: var(--space-2); list-style: none; margin: var(--space-3) 0 0; padding: 0; }
	li { border-left: 3px solid var(--danger); border-radius: var(--radius-sm); background: color-mix(in srgb, var(--danger) 5%, transparent); padding: var(--space-3); }
	li.info { border-left-color: var(--ink-3); }
	.issue-head { display: flex; gap: var(--space-2); align-items: baseline; }
	.severity { color: var(--danger); font-size: 0.75rem; font-weight: 700; text-transform: uppercase; }
	.info .severity { color: var(--ink-3); }
	button { margin-top: var(--space-2); border: 0; border-radius: var(--radius-sm); background: var(--accent); color: white; padding: 0.4rem 0.7rem; cursor: pointer; }
</style>
