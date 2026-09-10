<script lang="ts">
	interface Props {
		items: string[];
		ordered?: boolean;
		ariaLabel?: string;
		onChange?: (items: string[]) => void;
	}

	let {
		items = $bindable<string[]>([]),
		ordered = false,
		ariaLabel = 'List items',
		onChange = undefined
	}: Props = $props();

	function setItem(index: number, value: string) {
		const next = items.map((item, i) => (i === index ? value : item));
		items = next;
		onChange?.(next);
	}

	function addItem() {
		const next = [...items, ''];
		items = next;
		onChange?.(next);
	}

	function removeItem(index: number) {
		if (items.length <= 1) return;
		const next = items.filter((_, i) => i !== index);
		items = next;
		onChange?.(next);
	}
</script>

<div
	class="list-editor"
	data-testid="list-editor"
	data-ordered={ordered ? 'true' : 'false'}
	aria-label={ariaLabel}
>
	{#each items as item, index (index)}
		<div class="row">
			<span class="marker" aria-hidden="true">{ordered ? `${index + 1}.` : '•'}</span>
			<input
				type="text"
				class="item-input"
				value={item}
				aria-label={`Item ${index + 1}`}
				oninput={(e) => setItem(index, (e.currentTarget as HTMLInputElement).value)}
			/>
			<button
				type="button"
				class="remove"
				aria-label={`Remove item ${index + 1}`}
				disabled={items.length <= 1}
				onclick={() => removeItem(index)}
			>
				×
			</button>
		</div>
	{/each}
	<button type="button" class="add" data-testid="list-editor-add" onclick={addItem}>
		Add item
	</button>
</div>

<style>
	.list-editor {
		display: grid;
		gap: 8px;
	}
	.row {
		display: grid;
		grid-template-columns: auto 1fr auto;
		gap: 8px;
		align-items: center;
	}
	.marker {
		color: var(--ink-3, #666);
		font: 500 12px 'IBM Plex Mono', monospace;
		min-width: 1.5em;
	}
	.item-input {
		width: 100%;
		box-sizing: border-box;
		padding: 8px 10px;
		border: 1px solid var(--rule, #ccc);
		border-radius: 8px;
		background: var(--paper, #fff);
		color: var(--ink, #1a1a1a);
		font: inherit;
		font-size: 14px;
	}
	.remove,
	.add {
		border: 1px solid var(--rule, #ccc);
		border-radius: 8px;
		background: var(--surface, #f7f7f5);
		color: var(--ink-2, #444);
		cursor: pointer;
		font: inherit;
	}
	.remove {
		width: 32px;
		height: 32px;
	}
	.add {
		justify-self: start;
		padding: 6px 10px;
		font-size: 12px;
	}
	.remove:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
</style>
