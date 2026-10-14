<script lang="ts">
	import { untrack } from 'svelte';
	import type { ItemResults, KindProgress, LearnerResponse } from '../types';
	import InlineMarkup from '$lib/learn/document/renderers/InlineMarkup.svelte';
	import MarkBadge from './MarkBadge.svelte';
	import { listResults } from './shared';

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
		itemResults = null,
		initialResponse = null,
		response = $bindable({}),
		progress = $bindable({ done: 0, total: 1 })
	}: Props = $props();

	const count = $derived.by(() => {
		const answers = Array.isArray(config.answers) ? config.answers : [];
		const ids = Array.isArray(config.blank_ids) ? config.blank_ids : [];
		const declared = typeof config.blank_count === 'number' ? config.blank_count : 0;
		return Math.max(answers.length, ids.length, declared, 1);
	});

	/** Optional sentence with [1]..[n] markers: text segments and gap indexes (0-based). */
	const segments = $derived.by((): Array<{ gap?: number; text?: string }> | null => {
		const s = typeof config.sentence === 'string' ? config.sentence : '';
		if (!s || !/\[\d+\]/.test(s)) return null;
		return s.split(/\[(\d+)\]/).map((part, i) =>
			i % 2 === 1 ? { gap: Number(part) - 1 } : { text: part }
		);
	});

	let blanks = $state<string[]>([]);
	const marks = $derived(listResults(itemResults));

	function sized(list: string[], n: number): string[] {
		return Array.from({ length: n }, (_, i) => list[i] ?? '');
	}

	export function load(saved: LearnerResponse | null | undefined) {
		const b = saved?.blanks;
		blanks = sized(Array.isArray(b) ? b.map(String) : [], count);
	}
	export function reset() {
		blanks = sized([], count);
	}
	/** Keep the blanks that were right; clear the wrong ones. */
	export function keepCorrect(results?: ItemResults) {
		const list = listResults(results);
		blanks = sized(blanks.map((b, i) => (list?.[i] === true ? b : '')), count);
	}

	untrack(() => load(initialResponse));

	$effect(() => {
		if (blanks.length !== count) blanks = sized(blanks, count);
	});

	$effect(() => {
		response = { blanks };
		progress = { done: blanks.filter((b) => b.trim().length > 0).length, total: count };
	});
</script>

{#snippet gapInput(i: number, label: string, inline: boolean)}
	{@const mark = marks ? (marks[i] ? 'right' : 'wrong') : undefined}
	<input
		type="text"
		class:inline
		aria-label={label}
		value={blanks[i] ?? ''}
		data-mark={mark}
		style:width={inline ? `${Math.max(6, (blanks[i] ?? '').length + 2)}ch` : undefined}
		{disabled}
		oninput={(e) => {
			const next = [...blanks];
			next[i] = (e.currentTarget as HTMLInputElement).value;
			blanks = next;
		}}
	/>
	{#if mark}<MarkBadge {mark} />{/if}
{/snippet}

{#if segments}
	<p class="sentence" data-testid="fill-blank-interaction">
		{#each segments as seg, k (k)}
			{#if seg.gap !== undefined}
				{#if seg.gap >= 0 && seg.gap < blanks.length}
					<span class="gap">{@render gapInput(seg.gap, `Gap ${seg.gap + 1}`, true)}</span>
				{/if}
			{:else if seg.text}
				<span><InlineMarkup value={seg.text} /></span>
			{/if}
		{/each}
	</p>
{:else}
	<div class="blanks" data-testid="fill-blank-interaction">
		{#each blanks as _, i (i)}
			<div class="blank-row">
				<span class="blank-num" aria-hidden="true">{i + 1}</span>
				{@render gapInput(i, `Blank ${i + 1}`, false)}
			</div>
		{/each}
	</div>
{/if}

<style>
	.sentence {
		margin: 0;
		line-height: 2.6;
		font-size: 18px;
	}
	.gap {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		margin: 0 4px;
		vertical-align: middle;
		line-height: 1;
	}
	.gap input.inline {
		width: 6ch;
		max-width: 100%;
		min-width: 6ch;
		text-align: center;
		border-bottom: 3px solid var(--ink, #1c2321);
	}
	.blanks {
		display: grid;
		gap: 10px;
	}
	.blank-row {
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.blank-num {
		display: grid;
		place-items: center;
		flex: 0 0 28px;
		width: 28px;
		height: 28px;
		border-radius: 50%;
		background: var(--sand, #f3eee3);
		font-weight: 700;
	}
</style>
