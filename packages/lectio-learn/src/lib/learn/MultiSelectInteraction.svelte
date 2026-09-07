<script lang="ts">
	/**
	 * Compact multi-select interaction (Phase 04).
	 * Keyboard operable; evaluates via LearnInteractionContract.
	 */
	import {
		evaluateMultiSelect,
		type FeedbackSpec
	} from '$lib/learn/interaction-contract';

	interface Option {
		id: string;
		text: string;
	}

	interface Props {
		prompt: string;
		options: Option[];
		correctOptionIds: string[];
		feedback: FeedbackSpec;
		ariaLabel?: string;
	}

	let {
		prompt,
		options,
		correctOptionIds,
		feedback,
		ariaLabel = prompt
	}: Props = $props();

	let selected = $state<string[]>([]);
	let submitted = $state(false);
	const result = $derived(
		submitted
			? evaluateMultiSelect(
					{ correct_option_ids: correctOptionIds },
					{ selected_option_ids: selected },
					feedback
				)
			: null
	);

	function toggle(id: string) {
		if (submitted) return;
		selected = selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id];
	}

	function onKeydown(event: KeyboardEvent, id: string) {
		if (event.key === ' ' || event.key === 'Enter') {
			event.preventDefault();
			toggle(id);
		}
	}
</script>

<div class="ms-root" role="group" aria-label={ariaLabel}>
	<p class="prompt">{prompt}</p>
	<ul class="options">
		{#each options as option (option.id)}
			<li>
				<button
					type="button"
					class="option"
					class:selected={selected.includes(option.id)}
					aria-pressed={selected.includes(option.id)}
					disabled={submitted}
					onclick={() => toggle(option.id)}
					onkeydown={(e) => onKeydown(e, option.id)}
				>
					{option.text}
				</button>
			</li>
		{/each}
	</ul>
	<button type="button" class="submit" disabled={submitted || selected.length === 0} onclick={() => (submitted = true)}>
		Check
	</button>
	{#if result}
		<p class="feedback" data-outcome={result.outcome} role="status">{result.feedback}</p>
	{/if}
</div>

<style>
	.ms-root {
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
	.options {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 8px;
	}
	.option {
		width: 100%;
		text-align: left;
		border: 1px solid var(--rule, #d6d3d1);
		border-radius: 10px;
		background: var(--paper, #fafaf9);
		padding: 10px 12px;
		cursor: pointer;
	}
	.option.selected {
		border-color: var(--accent, #0f766e);
		background: color-mix(in srgb, var(--accent, #0f766e) 12%, white);
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
