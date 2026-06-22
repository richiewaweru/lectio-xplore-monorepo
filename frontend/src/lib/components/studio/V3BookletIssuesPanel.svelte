<script lang="ts">
	interface Props {
		issues?: Array<Record<string, unknown>>;
		title?: string;
	}

	let { issues = [], title = 'Issues to review' }: Props = $props();

	function asText(value: unknown): string {
		return typeof value === 'string' ? value.trim() : '';
	}

	function issueMeta(issue: Record<string, unknown>): string {
		return [asText(issue.section_id), asText(issue.category)].filter(Boolean).join(' - ');
	}
</script>

{#if issues.length}
	<section class="rounded-lg border border-border/60 bg-card px-4 py-3 text-sm">
		<p class="font-semibold">{title}</p>
		<ul class="mt-3 space-y-2">
			{#each issues as issue}
				<li class="rounded-md border border-border/40 bg-background/60 px-3 py-2">
					<p class="font-medium">{String(issue.message ?? 'Unknown issue')}</p>
					{#if issueMeta(issue)}
						<p class="mt-1 text-xs text-muted-foreground">{issueMeta(issue)}</p>
					{/if}
				</li>
			{/each}
		</ul>
	</section>
{/if}
