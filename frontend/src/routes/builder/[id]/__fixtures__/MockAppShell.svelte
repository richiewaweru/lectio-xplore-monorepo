<script lang="ts">
	export let document: { title?: string } | null = null;
	export let pendingPlan: Array<{ id: string; title: string }> = [];
</script>

<div data-testid="mock-app-shell">Builder shell: {document?.title ?? 'Untitled lesson'}</div>
{#each pendingPlan as section (section.id)}
	<div data-testid={`mock-pending-${section.id}`}>{section.title} — Generating…</div>
{/each}
