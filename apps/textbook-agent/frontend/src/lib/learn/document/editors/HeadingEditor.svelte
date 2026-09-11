<script lang="ts">
	interface Props {
		value: string;
		level?: 1 | 2 | 3;
		ariaLabel?: string;
		onChange?: (value: string) => void;
		onLevelChange?: (level: 1 | 2 | 3) => void;
	}

	let {
		value = $bindable(''),
		level = $bindable<1 | 2 | 3>(2),
		ariaLabel = 'Heading text',
		onChange = undefined,
		onLevelChange = undefined
	}: Props = $props();
</script>

<div class="heading-editor" data-testid="heading-editor">
	<label class="level">
		<span class="sr">Level</span>
		<select
			aria-label="Heading level"
			value={level}
			onchange={(e) => {
				const next = Number((e.currentTarget as HTMLSelectElement).value) as 1 | 2 | 3;
				level = next;
				onLevelChange?.(next);
			}}
		>
			<option value={1}>H1</option>
			<option value={2}>H2</option>
			<option value={3}>H3</option>
		</select>
	</label>
	<input
		type="text"
		class="text"
		aria-label={ariaLabel}
		{value}
		oninput={(e) => {
			const next = (e.currentTarget as HTMLInputElement).value;
			value = next;
			onChange?.(next);
		}}
	/>
</div>

<style>
	.heading-editor {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 8px;
		align-items: center;
	}
	.level select,
	.text {
		box-sizing: border-box;
		border: 1px solid var(--rule, #ccc);
		border-radius: 10px;
		background: var(--paper, #fff);
		color: var(--ink, #1a1a1a);
		font: inherit;
		padding: 8px 10px;
	}
	.text {
		width: 100%;
		font-family: Fraunces, Georgia, serif;
		font-size: 18px;
	}
	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
	}
</style>
