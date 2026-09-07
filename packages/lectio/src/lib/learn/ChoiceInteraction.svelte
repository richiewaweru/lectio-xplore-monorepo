<script lang="ts">
	import { evaluateChoice, type FeedbackSpec } from '$lib/learn/interaction-contract';

	interface Option {
		id: string;
		text: string;
		imageUrl?: string;
	}

	interface Props {
		prompt: string;
		options: Option[];
		correctOptionId: string;
		feedback: FeedbackSpec;
		ariaLabel?: string;
		variant?: 'text' | 'image';
	}

	let {
		prompt,
		options,
		correctOptionId,
		feedback,
		ariaLabel = prompt,
		variant = 'text'
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

	function select(id: string) {
		if (submitted) return;
		selected = id;
	}

	function onKeydown(event: KeyboardEvent, id: string) {
		if (event.key === ' ' || event.key === 'Enter') {
			event.preventDefault();
			select(id);
		}
	}
</script>

<div class="choice-root" role="radiogroup" aria-label={ariaLabel} data-testid="choice-interaction">
	<p class="prompt">{prompt}</p>
	<ul class="options" class:image-grid={variant === 'image'}>
		{#each options as option (option.id)}
			<li>
				<button
					type="button"
					class="option"
					class:selected={selected === option.id}
					role="radio"
					aria-checked={selected === option.id}
					disabled={submitted}
					onclick={() => select(option.id)}
					onkeydown={(e) => onKeydown(e, option.id)}
				>
					{#if variant === 'image' && option.imageUrl}
						<img src={option.imageUrl} alt={option.text} />
					{/if}
					<span>{option.text}</span>
				</button>
			</li>
		{/each}
	</ul>
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
	.choice-root {
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
	.options.image-grid {
		grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
	}
	.option {
		width: 100%;
		text-align: left;
		border: 1px solid var(--rule, #d6d3d1);
		border-radius: 10px;
		background: var(--paper, #fafaf9);
		padding: 10px 12px;
		cursor: pointer;
		display: grid;
		gap: 8px;
	}
	.option img {
		width: 100%;
		height: 80px;
		object-fit: cover;
		border-radius: 8px;
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
