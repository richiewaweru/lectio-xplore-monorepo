<script lang="ts">
	interface Props {
		caption?: string;
		alt?: string;
		assetId?: string | null;
		onChange?: (patch: { caption?: string; alt?: string; asset_id?: string | null }) => void;
	}

	let {
		caption = $bindable(''),
		alt = $bindable(''),
		assetId = $bindable<string | null>(null),
		onChange = undefined
	}: Props = $props();
</script>

<div class="figure-editor" data-testid="figure-editor">
	<label>
		<span>Asset id / URL</span>
		<input
			type="text"
			aria-label="Figure asset id"
			value={assetId ?? ''}
			oninput={(e) => {
				const next = (e.currentTarget as HTMLInputElement).value.trim() || null;
				assetId = next;
				onChange?.({ asset_id: next });
			}}
		/>
	</label>
	<label>
		<span>Caption</span>
		<input
			type="text"
			aria-label="Figure caption"
			value={caption}
			oninput={(e) => {
				const next = (e.currentTarget as HTMLInputElement).value;
				caption = next;
				onChange?.({ caption: next });
			}}
		/>
	</label>
	<label>
		<span>Alt text</span>
		<input
			type="text"
			aria-label="Figure alt"
			value={alt}
			oninput={(e) => {
				const next = (e.currentTarget as HTMLInputElement).value;
				alt = next;
				onChange?.({ alt: next });
			}}
		/>
	</label>
</div>

<style>
	.figure-editor {
		display: grid;
		gap: 8px;
	}
	label {
		display: grid;
		gap: 4px;
		font-size: 12px;
		color: var(--ink-3, #666);
	}
	input {
		box-sizing: border-box;
		width: 100%;
		border: 1px solid var(--rule, #ccc);
		border-radius: 10px;
		background: var(--paper, #fff);
		color: var(--ink, #1a1a1a);
		font: inherit;
		padding: 8px 10px;
	}
</style>
