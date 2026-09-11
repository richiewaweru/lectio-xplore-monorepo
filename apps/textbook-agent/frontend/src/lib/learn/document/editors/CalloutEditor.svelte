<script lang="ts">
	import type { CalloutTone } from '../types';

	interface Props {
		body: string;
		title?: string;
		tone?: CalloutTone;
		onChange?: (patch: { body?: string; title?: string; tone?: CalloutTone }) => void;
	}

	let {
		body = $bindable(''),
		title = $bindable(''),
		tone = $bindable<CalloutTone>('note'),
		onChange = undefined
	}: Props = $props();

	const tones: CalloutTone[] = ['note', 'warning', 'tip', 'important'];
</script>

<div class="callout-editor" data-testid="callout-editor" data-tone={tone}>
	<div class="row">
		<select
			aria-label="Callout tone"
			value={tone}
			onchange={(e) => {
				const next = (e.currentTarget as HTMLSelectElement).value as CalloutTone;
				tone = next;
				onChange?.({ tone: next });
			}}
		>
			{#each tones as t}
				<option value={t}>{t}</option>
			{/each}
		</select>
		<input
			type="text"
			placeholder="Title (optional)"
			aria-label="Callout title"
			value={title}
			oninput={(e) => {
				const next = (e.currentTarget as HTMLInputElement).value;
				title = next;
				onChange?.({ title: next });
			}}
		/>
	</div>
	<textarea
		aria-label="Callout body"
		rows={3}
		value={body}
		oninput={(e) => {
			const next = (e.currentTarget as HTMLTextAreaElement).value;
			body = next;
			onChange?.({ body: next });
		}}
	></textarea>
</div>

<style>
	.callout-editor {
		display: grid;
		gap: 8px;
	}
	.row {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 8px;
	}
	select,
	input,
	textarea {
		box-sizing: border-box;
		width: 100%;
		border: 1px solid var(--rule, #ccc);
		border-radius: 10px;
		background: var(--paper, #fff);
		color: var(--ink, #1a1a1a);
		font: inherit;
		padding: 8px 10px;
	}
	textarea {
		resize: vertical;
		min-height: 72px;
		line-height: 1.55;
	}
</style>
