<script lang="ts">
	import type { EquationNode } from '../types';
	import InlineMarkup from './InlineMarkup.svelte';
	interface Props { node: EquationNode; }
	let { node }: Props = $props();
</script>

<figure class="learn-equation" data-testid="equation-node">
	{#if node.label}<figcaption><InlineMarkup value={node.label} /></figcaption>{/if}
	<div class="equation-line">
		<div class="equation-terms">
			{#each node.inputs as input, index (index)}<span class="term"><InlineMarkup value={input} /></span>{/each}
		</div>
		<div class="arrow-wrap">
			{#if node.condition}<span class="condition"><InlineMarkup value={node.condition} /></span>{/if}
			<span class="arrow" aria-hidden="true">→</span>
		</div>
		<div class="equation-terms">
			{#each node.outputs as output, index (index)}<span class="term"><InlineMarkup value={output} /></span>{/each}
		</div>
	</div>
</figure>

<style>
	.learn-equation { margin: 0; padding: 22px 24px; border: 1px solid var(--ink, #1c2321); border-radius: 14px; background: var(--surface, #fff); }
	.learn-equation figcaption { margin-bottom: 14px; color: var(--muted, #5b6460); font-size: 14px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
	.equation-line { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 18px; }
	.equation-terms { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; }
	.term { border: 1px solid var(--rule-strong, #c9c3b5); border-radius: 999px; padding: 8px 13px; font-size: 18px; text-align: center; }
	.arrow-wrap { display: grid; justify-items: center; gap: 1px; min-width: 110px; }
	.arrow { font-size: 34px; line-height: 1; }
	.condition { color: var(--green, #1b5e40); font-size: 14px; font-weight: 700; text-align: center; }
	@media (max-width: 600px) { .equation-line { grid-template-columns: 1fr; gap: 10px; } .arrow { transform: rotate(90deg); } }
</style>
