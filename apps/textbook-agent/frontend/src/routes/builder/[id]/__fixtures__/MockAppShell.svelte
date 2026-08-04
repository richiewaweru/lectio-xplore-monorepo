<script lang="ts">
	export let document: { title?: string; sections?: Array<{ id: string }> } | null = null;
	export let pendingPlan: Array<{ id: string; title: string }> = [];
	export let sectionProgress: Record<string, string> = {};
	export let generationTerminal = false;
	export let documentLevelIssues: Array<{ id: string; message: string }> = [];
	export let onDismissDocumentIssue: (issueId: string) => void = () => {};
</script>

<div data-testid="mock-app-shell">Builder shell: {document?.title ?? 'Untitled lesson'}</div>
{#if pendingPlan.length > 0 && !generationTerminal}
	<div data-testid="mock-progress-summary">{pendingPlan.filter((section) => sectionProgress[section.id] === 'ready').length}/{pendingPlan.length} sections ready</div>
	{#each pendingPlan.filter((section) => !(document?.sections ?? []).some((real) => real.id === section.id)) as section (section.id)}
		<div data-testid={`mock-pending-${section.id}`}>{section.title} — Generating…</div>
	{/each}
{/if}
{#each documentLevelIssues as issue (issue.id)}
	<div>{issue.message}<button type="button" onclick={() => onDismissDocumentIssue(issue.id)}>Dismiss lesson issue</button></div>
{/each}
