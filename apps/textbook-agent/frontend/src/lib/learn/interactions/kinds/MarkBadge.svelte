<script lang="ts">
	/** Per-item result after a check: a glyph plus screen-reader text, never colour alone. */
	interface Props {
		mark?: 'right' | 'wrong' | 'missed' | undefined;
	}
	let { mark = undefined }: Props = $props();

	const glyph = $derived(mark === 'right' ? '✓' : mark === 'wrong' ? '✗' : '!');
	const text = $derived(
		mark === 'right' ? 'correct' : mark === 'wrong' ? 'not correct' : 'missed: this one was needed'
	);
</script>

{#if mark}
	<span class="glyph" data-mark-glyph={mark} aria-hidden="true">{glyph}</span>
	<span class="hidden-text" data-mark-text>{text}</span>
{/if}

<style>
	.glyph {
		display: inline-grid;
		place-items: center;
		flex: 0 0 24px;
		width: 24px;
		height: 24px;
		border-radius: 50%;
		font-size: 14px;
		font-weight: 800;
		line-height: 1;
		color: #fff;
		background: #b3261e;
	}
	.glyph[data-mark-glyph='right'] {
		background: #1b5e40;
	}
	.hidden-text {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}
</style>
