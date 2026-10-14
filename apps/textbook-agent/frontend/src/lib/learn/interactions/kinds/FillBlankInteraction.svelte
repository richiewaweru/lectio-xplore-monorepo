<script lang="ts">
	import { untrack } from 'svelte';
	import type { ItemResults, KindProgress, LearnerResponse } from '../types';
	import InlineMarkup from '$lib/learn/document/renderers/InlineMarkup.svelte';
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

{#snippet gapInput(i: number, label: string)}
	<input
		type="text"
		aria-label={label}
		value={blanks[i] ?? ''}
		data-mark={marks ? (marks[i] ? 'right' : 'wrong') : undefined}
		{disabled}
		oninput={(e) => {
			const next = [...blanks];
			next[i] = (e.currentTarget as HTMLInputElement).value;
			blanks = next;
		}}
	/>
{/snippet}

{#if segments}
	<p class="sentence" data-testid="fill-blank-interaction">
		{#each segments as seg, k (k)}
			{#if seg.gap !== undefined}
				{#if seg.gap >= 0 && seg.gap < blanks.length}
					<span class="gap">{@render gapInput(seg.gap, `Gap ${seg.gap + 1}`)}</span>
				{/if}
			{:else if seg.text}
				<span><InlineMarkup value={seg.text} /></span>
			{/if}
		{/each}
	</p>
{:else}
	<div class="blanks" data-testid="fill-blank-interaction">
		{#each blanks as _, i (i)}
			<label class="field">
				<span class="sr">Blank {i + 1}</span>
				{@render gapInput(i, `Blank ${i + 1}`)}
			</label>
		{/each}
	</div>
{/if}

<style>
	.sentence {
		margin: 0;
		line-height: 2.4;
		font-size: 18px;
	}
	.gap {
		display: inline-block;
		margin: 0 4px;
		vertical-align: middle;
	}
	.gap :global(input) {
		width: 9em;
	}
</style>
