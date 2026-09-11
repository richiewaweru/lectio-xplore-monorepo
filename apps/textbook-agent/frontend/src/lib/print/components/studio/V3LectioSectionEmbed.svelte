<script lang="ts">
	/**
	 * Studio canvas section preview without @lectio/learn templates.
	 * Full print rendering uses LectioPageDocumentView / @lectio/page.
	 */
	interface Props {
		templateId: string;
		sectionId: string;
		title: string;
		mergedFields: Record<string, unknown>;
	}

	let { templateId, sectionId, title, mergedFields }: Props = $props();

	const fieldKeys = $derived(Object.keys(mergedFields ?? {}).slice(0, 12));
</script>

<article class="section-embed" data-section-id={sectionId} data-template-id={templateId}>
	<p class="eyebrow">{templateId}</p>
	<h3>{title || sectionId}</h3>
	{#if fieldKeys.length}
		<ul>
			{#each fieldKeys as key}
				<li><code>{key}</code></li>
			{/each}
		</ul>
	{:else}
		<p class="muted">No merged fields yet.</p>
	{/if}
</article>

<style>
	.section-embed {
		display: grid;
		gap: 8px;
		padding: 12px 14px;
		border: 1px solid var(--rule, #e5e7eb);
		border-radius: 10px;
		background: var(--surface, #fff);
	}
	.eyebrow {
		margin: 0;
		font: 500 11px 'IBM Plex Mono', monospace;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--ink-3, #6b7280);
	}
	h3 {
		margin: 0;
		font-size: 1rem;
	}
	ul {
		margin: 0;
		padding-left: 1.1rem;
		font-size: 0.8rem;
		color: var(--ink-2, #4b5563);
	}
	.muted {
		margin: 0;
		font-size: 0.85rem;
		color: var(--ink-3, #6b7280);
	}
</style>
