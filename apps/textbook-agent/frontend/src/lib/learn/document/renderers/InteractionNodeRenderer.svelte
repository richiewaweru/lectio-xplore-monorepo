<script lang="ts">
	/**
	 * Interaction island placeholder for LearnDocument v2.
	 * Retained shells still live in @lectio/learn; full prop-mapping mount is deferred.
	 * Until then we surface type + prompt with a clear stub for missing shells.
	 */
	import type { InteractionNode, InteractionType } from '../types';

	interface Props {
		node: InteractionNode;
	}

	let { node }: Props = $props();

	/** Types that still export a dedicated Svelte shell from @lectio/learn. */
	const SHELL_EXPORTS: Partial<Record<InteractionType, string>> = {
		choice: 'ChoiceInteraction',
		'multi-select': 'MultiSelectInteraction',
		classify: 'ClassifyInteraction',
		'match-pairs': 'MatchPairsInteraction',
		sequence: 'SequenceInteraction',
		numeric: 'NumericInteraction',
		'short-response': 'ShortResponseInteraction'
		// fill-blank: no dedicated Interaction.svelte export today
	};

	const shellName = $derived(SHELL_EXPORTS[node.interaction_type] ?? null);
	const prompt = $derived(node.prompt?.trim() || 'No prompt');

	let mountedLabel = $state<string | null>(null);

	$effect(() => {
		const type = node.interaction_type;
		const exportName = SHELL_EXPORTS[type];
		if (!exportName) {
			mountedLabel = null;
			return;
		}
		let cancelled = false;
		import('@lectio/learn')
			.then((mod) => {
				if (cancelled) return;
				const component = (mod as Record<string, unknown>)[exportName];
				mountedLabel = typeof component !== 'undefined' ? exportName : null;
			})
			.catch(() => {
				if (!cancelled) mountedLabel = null;
			});
		return () => {
			cancelled = true;
		};
	});
</script>

<section
	class="interaction-node"
	data-testid="interaction-node-renderer"
	data-interaction-type={node.interaction_type}
	data-node-id={node.id}
	data-shell={shellName ?? 'none'}
>
	<p class="eyebrow">{node.interaction_type}</p>
	<p class="prompt">{prompt}</p>
	{#if mountedLabel}
		<p class="status" data-testid="interaction-shell-available">
			Retained shell available ({mountedLabel}) — mount deferred to interaction wiring.
		</p>
	{:else}
		<div class="stub" data-testid="interaction-node-stub">
			<p>Interaction stub — config-driven mount not wired yet.</p>
			{#if node.config && Object.keys(node.config).length > 0}
				<p class="meta">{Object.keys(node.config).length} config keys</p>
			{/if}
		</div>
	{/if}
</section>

<style>
	.interaction-node {
		margin: 0;
		padding: 14px;
		border: 1px dashed var(--rule, #ccc);
		border-radius: 10px;
		background: var(--surface, #f7f7f5);
		display: grid;
		gap: 8px;
	}
	.eyebrow {
		margin: 0;
		color: var(--ink-3, #666);
		font: 500 11px 'IBM Plex Mono', monospace;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}
	.prompt {
		margin: 0;
		font-size: 15px;
		line-height: 1.5;
		color: var(--ink, #1a1a1a);
	}
	.status,
	.stub {
		margin: 0;
		font-size: 12px;
		line-height: 1.45;
		color: var(--ink-2, #444);
	}
	.stub {
		padding: 8px 10px;
		border-radius: 8px;
		background: var(--paper, #fff);
		border: 1px solid var(--rule, #ccc);
	}
	.stub p {
		margin: 0;
	}
	.meta {
		margin-top: 4px !important;
		color: var(--ink-3, #666);
		font: 500 11px 'IBM Plex Mono', monospace;
	}
</style>
