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

	function issueMessage(issue: Record<string, unknown>): string {
		if (asText(issue.category) === 'visual_generation_failed' && asText(issue.message).startsWith('image omitted by quality gate:')) {
			const section = asText(issue.section_id) || 'this section';
			return `The image for '${section}' didn't meet quality standards and was left out — you can regenerate it or print text-only.`;
		}
		return String(issue.message ?? 'Unknown issue');
	}
</script>

{#if issues.length}
	<section class="rounded-lg border border-border/60 bg-card px-4 py-3 text-sm">
		<p class="font-semibold">{title}</p>
		<ul class="mt-3 space-y-2">
			{#each issues as issue}
				<li class="rounded-md border border-border/40 bg-background/60 px-3 py-2">
					<p class="font-medium">{issueMessage(issue)}</p>
					{#if issueMeta(issue)}
						<p class="mt-1 text-xs text-muted-foreground">{issueMeta(issue)}</p>
					{/if}
				</li>
			{/each}
		</ul>
	</section>
{/if}
