<script lang="ts">
	import { evaluateChoice, type FeedbackSpec } from '$lib/learn/interaction-contract';

	interface Hotspot {
		id: string;
		label: string;
		x: number;
		y: number;
	}

	interface Props {
		prompt: string;
		imageUrl: string;
		imageAlt: string;
		hotspots: Hotspot[];
		correctOptionId: string;
		feedback: FeedbackSpec;
		ariaLabel?: string;
	}

	let {
		prompt,
		imageUrl,
		imageAlt,
		hotspots,
		correctOptionId,
		feedback,
		ariaLabel = prompt
	}: Props = $props();

	let selected = $state<string | null>(null);
	let submitted = $state(false);
	const result = $derived(
		submitted && selected
			? evaluateChoice(
					{ correct_option_id: correctOptionId },
					{ selected_option_id: selected },
					feedback
				)
			: null
	);
</script>

<div class="hotspot-root" aria-label={ariaLabel} data-testid="hotspot-interaction">
	<p class="prompt">{prompt}</p>
	<div class="frame">
		<img src={imageUrl} alt={imageAlt} />
		{#each hotspots as spot (spot.id)}
			<button
				type="button"
				class="spot"
				class:selected={selected === spot.id}
				style={`left:${spot.x}%;top:${spot.y}%`}
				aria-label={spot.label}
				aria-pressed={selected === spot.id}
				disabled={submitted}
				onclick={() => (selected = spot.id)}
			>
				{spot.label}
			</button>
		{/each}
	</div>
	<button
		type="button"
		class="submit"
		disabled={submitted || selected === null}
		onclick={() => (submitted = true)}
	>
		Check
	</button>
	{#if result}
		<p class="feedback" data-outcome={result.outcome} role="status">{result.feedback}</p>
	{/if}
</div>

<style>
	.hotspot-root {
		display: grid;
		gap: 12px;
		border: 1px solid var(--rule, #d6d3d1);
		border-radius: 12px;
		background: var(--surface, #fff);
		padding: 14px;
		color: var(--ink, #1c1917);
	}
	.prompt {
		margin: 0;
		font-weight: 600;
	}
	.frame {
		position: relative;
		border-radius: 10px;
		overflow: hidden;
		border: 1px solid var(--rule, #d6d3d1);
	}
	.frame img {
		display: block;
		width: 100%;
		height: auto;
	}
	.spot {
		position: absolute;
		transform: translate(-50%, -50%);
		border: 2px solid white;
		border-radius: 999px;
		background: color-mix(in srgb, var(--accent, #0f766e) 80%, black);
		color: white;
		font-size: 11px;
		padding: 6px 8px;
		cursor: pointer;
	}
	.spot.selected {
		outline: 2px solid var(--amber, #d97706);
	}
	.submit {
		justify-self: start;
		border: 1px solid var(--accent, #0f766e);
		border-radius: 8px;
		background: var(--accent, #0f766e);
		color: white;
		padding: 8px 12px;
		font-weight: 600;
		cursor: pointer;
	}
	.feedback {
		margin: 0;
		font-size: 14px;
	}
</style>
