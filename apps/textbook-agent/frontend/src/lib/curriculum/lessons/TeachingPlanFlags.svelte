<script lang="ts">
	import type { TeachingPlanFlag } from './teaching-plan-review';

	let { flags = [] }: { flags?: TeachingPlanFlag[] } = $props();

	function where(flag: TeachingPlanFlag): string {
		const parts: string[] = [];
		if (flag.section_ids?.length) parts.push(`Section: ${flag.section_ids.join(', ')}`);
		if (flag.block_ids?.length) parts.push(`Block: ${flag.block_ids.join(', ')}`);
		return parts.join(' · ');
	}
</script>

{#if flags.length}
	<aside class="notes" aria-label="Reviewer notes">
		<h3>Reviewer notes ({flags.length})</h3>
		<p class="lede">These are suggestions, not blockers. You can approve the plan as it is.</p>
		<ul>
			{#each flags as flag, index (index)}
				<li>
					<p class="message">{flag.message}</p>
					{#if where(flag)}<p class="where">{where(flag)}</p>{/if}
					{#if flag.repair_instruction && flag.repair_instruction !== flag.message}
						<p class="suggestion"><strong>Suggestion:</strong> {flag.repair_instruction}</p>
					{/if}
				</li>
			{/each}
		</ul>
	</aside>
{/if}

<style>
	.notes {
		border: 1px solid var(--amber, #b7791f);
		border-radius: var(--radius-md);
		padding: var(--space-3) var(--space-4);
		background: var(--surface);
	}
	h3 {
		margin: 0 0 0.25rem;
		font-size: 1rem;
		color: var(--amber, #b7791f);
	}
	.lede,
	.message,
	.where,
	.suggestion {
		margin: 0 0 0.35rem;
		font-size: 0.875rem;
		color: var(--ink-2);
	}
	.where {
		font-size: 0.75rem;
		color: var(--ink-3);
	}
	ul {
		margin: 0.5rem 0 0;
		padding-left: 1.1rem;
		display: grid;
		gap: 0.6rem;
	}
</style>
