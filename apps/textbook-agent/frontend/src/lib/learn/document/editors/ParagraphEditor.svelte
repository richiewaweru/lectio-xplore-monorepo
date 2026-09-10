<script lang="ts">
	interface Props {
		value: string;
		placeholder?: string;
		ariaLabel?: string;
		onChange?: (value: string) => void;
		onBlur?: () => void;
	}

	let {
		value = $bindable(''),
		placeholder = 'Write a paragraph…',
		ariaLabel = 'Paragraph text',
		onChange = undefined,
		onBlur = undefined
	}: Props = $props();

	function handleInput(event: Event) {
		const next = (event.currentTarget as HTMLTextAreaElement).value;
		value = next;
		onChange?.(next);
	}
</script>

<textarea
	class="paragraph-editor"
	data-testid="paragraph-editor"
	{placeholder}
	aria-label={ariaLabel}
	{value}
	oninput={handleInput}
	onblur={() => onBlur?.()}
	rows={3}
></textarea>

<style>
	.paragraph-editor {
		display: block;
		width: 100%;
		box-sizing: border-box;
		margin: 0;
		padding: 10px 12px;
		border: 1px solid var(--rule, #ccc);
		border-radius: 10px;
		background: var(--paper, #fff);
		color: var(--ink, #1a1a1a);
		font: inherit;
		font-size: 15px;
		line-height: 1.6;
		resize: vertical;
		min-height: 72px;
	}
	.paragraph-editor:focus {
		outline: 2px solid var(--ink-3, #888);
		outline-offset: 1px;
	}
</style>
