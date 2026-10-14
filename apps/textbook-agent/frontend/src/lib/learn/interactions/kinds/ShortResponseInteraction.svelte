<script lang="ts">
	import { untrack } from 'svelte';
	import type { ItemResults, KindProgress, LearnerResponse } from '../types';

	interface Props {
		config: Record<string, unknown>;
		disabled?: boolean;
		itemResults?: ItemResults | undefined;
		initialResponse?: LearnerResponse | null;
		response?: LearnerResponse;
		progress?: KindProgress;
	}

	let {
		config,
		disabled = false,
		itemResults: _itemResults = null,
		initialResponse = null,
		response = $bindable({}),
		progress = $bindable({ done: 0, total: 1 })
	}: Props = $props();

	const uid = $props.id();
	const rows = $derived(
		typeof config.answer_lines === 'number' && config.answer_lines > 0
			? Math.min(Math.floor(config.answer_lines), 20)
			: 3
	);
	const placeholder = $derived(typeof config.placeholder === 'string' ? config.placeholder : '');
	const minLength = $derived(typeof config.min_length === 'number' ? config.min_length : undefined);
	const maxLength = $derived(typeof config.max_length === 'number' ? config.max_length : undefined);
	const teacherReview = $derived(config.evaluation === 'teacher-review');

	let text = $state('');
	const guide = $derived.by(() => {
		const n = text.length;
		if (maxLength !== undefined) return `${n} / ${maxLength} characters`;
		if (minLength !== undefined) return `${n} characters (at least ${minLength})`;
		return '';
	});

	export function load(saved: LearnerResponse | null | undefined) {
		const t = saved?.text;
		text = typeof t === 'string' ? t : '';
	}
	export function reset() {
		text = '';
	}
	export function keepCorrect(_results?: ItemResults) {
		text = '';
	}

	untrack(() => load(initialResponse));

	$effect(() => {
		response = { text };
		progress = { done: text.trim().length > 0 ? 1 : 0, total: 1 };
	});
</script>

<div class="field">
	<label class="field-label" for={`${uid}-answer`}>Answer</label>
	<textarea
		id={`${uid}-answer`}
		{rows}
		{placeholder}
		minlength={minLength}
		maxlength={maxLength}
		aria-describedby={`${uid}-notes`}
		bind:value={text}
		{disabled}
	></textarea>
	<div class="notes" id={`${uid}-notes`}>
		{#if guide}<span class="hint" data-testid="short-guide">{guide}</span>{/if}
		{#if teacherReview}<span class="hint" data-testid="teacher-note">Your teacher will read this.</span>{/if}
	</div>
</div>

<style>
	textarea {
		resize: vertical;
		line-height: 1.5;
	}
	.notes {
		display: flex;
		flex-wrap: wrap;
		gap: 4px 16px;
	}
</style>
