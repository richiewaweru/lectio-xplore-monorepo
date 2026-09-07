<script lang="ts">
	import type { StudentStage } from './student-shell';

	interface Props {
		stages: StudentStage[];
		currentIndex: number;
		onSelect: (index: number) => void;
	}

	let { stages, currentIndex, onSelect }: Props = $props();
	const activeStage = $derived(stages[currentIndex] ?? null);
</script>

<nav class="stage-tabs desktop-nav" aria-label="Lesson stages" data-testid="stage-tabs">
	{#each stages as stage (stage.section.id)}
		<button
			type="button"
			class:active={stage.index === currentIndex}
			data-assessment={stage.assessment_mode}
			onclick={() => onSelect(stage.index)}
		>
			<span class="idx">{stage.index + 1}</span>
			<span class="label">{stage.label}</span>
		</button>
	{/each}
</nav>

<nav class="stage-compact phone-nav" aria-label="Lesson stage" data-testid="stage-compact">
	<button type="button" class="nav-btn" disabled={currentIndex <= 0} onclick={() => onSelect(currentIndex - 1)}>
		Prev
	</button>
	<div class="compact-meta">
		<span class="eyebrow">Stage {currentIndex + 1} / {stages.length}</span>
		<strong>{activeStage?.label}</strong>
	</div>
	<button
		type="button"
		class="nav-btn"
		disabled={currentIndex >= stages.length - 1}
		onclick={() => onSelect(currentIndex + 1)}
	>
		Next
	</button>
</nav>

<style>
	.stage-tabs {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		border-bottom: 1px solid var(--rule);
		padding-bottom: 10px;
	}
	.stage-tabs button {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		border: 1px solid var(--rule);
		border-radius: 999px;
		background: var(--surface);
		color: var(--ink-2);
		padding: 8px 12px;
		font-size: 13px;
		font-weight: 600;
		cursor: pointer;
	}
	.stage-tabs button.active {
		border-color: var(--accent);
		background: var(--accent-soft, color-mix(in srgb, var(--accent) 12%, white));
		color: var(--accent);
	}
	.stage-tabs .idx {
		display: grid;
		place-items: center;
		width: 20px;
		height: 20px;
		border-radius: 50%;
		background: var(--paper);
		font: 500 10px 'IBM Plex Mono', monospace;
	}
	.stage-compact {
		display: none;
		grid-template-columns: auto 1fr auto;
		gap: 10px;
		align-items: center;
		border: 1px solid var(--rule);
		border-radius: 12px;
		background: var(--surface);
		padding: 10px 12px;
	}
	.nav-btn {
		border: 1px solid var(--rule);
		border-radius: 8px;
		background: var(--paper);
		color: var(--ink);
		padding: 8px 12px;
		font-size: 13px;
		font-weight: 600;
		cursor: pointer;
	}
	.nav-btn:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}
	.compact-meta {
		text-align: center;
	}
	.compact-meta .eyebrow {
		margin: 0 0 6px;
		color: var(--ink-3);
		font: 500 11px 'IBM Plex Mono', monospace;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}
	.compact-meta strong {
		display: block;
		font-size: 14px;
	}

	@media (max-width: 720px) {
		.desktop-nav {
			display: none;
		}
		.phone-nav {
			display: grid;
		}
	}

	@media (min-width: 721px) {
		.phone-nav {
			display: none;
		}
	}
</style>
