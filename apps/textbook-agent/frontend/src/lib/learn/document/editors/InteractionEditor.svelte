<script lang="ts">
	import type { InteractionNode } from '../types';

	interface Props {
		node: InteractionNode;
		onChange?: (patch: {
			prompt?: string;
			config?: Record<string, unknown>;
			feedback?: Record<string, unknown> | string | null;
		}) => void;
	}

	let { node, onChange }: Props = $props();

	const type = $derived(node.interaction_type);
	let prompt = $state(node.prompt ?? '');
	let optionsText = $state('');
	let correctText = $state('');
	let accepted = $state('');
	let pairsText = $state('');
	let categoriesText = $state('');
	let itemsText = $state('');
	let feedback = $state('');

	$effect(() => {
		prompt = node.prompt ?? '';
		const cfg = node.config ?? {};
		const opts = (cfg.options as Array<{ id?: string; label?: string; text?: string }> | string[]) ?? [];
		if (Array.isArray(opts)) {
			optionsText = opts
				.map((o) => (typeof o === 'string' ? o : o.label || o.text || o.id || ''))
				.filter(Boolean)
				.join('\n');
		}
		const correct = cfg.correct_option_ids ?? cfg.correct_answers ?? cfg.accepted_answers;
		if (Array.isArray(correct)) correctText = correct.map(String).join(', ');
		else if (typeof correct === 'string') correctText = correct;
		accepted = String(cfg.accepted_answer ?? cfg.expected_value ?? cfg.answer ?? '');
		const pairs = (cfg.pairs as Array<{ left?: string; right?: string }> | undefined) ?? [];
		pairsText = pairs.map((p) => `${p.left ?? ''} = ${p.right ?? ''}`).join('\n');
		const cats = (cfg.categories as string[] | undefined) ?? [];
		categoriesText = cats.join('\n');
		const items = (cfg.items as string[] | undefined) ?? (cfg.ordered_items as string[] | undefined) ?? [];
		itemsText = items.map(String).join('\n');
		feedback = typeof node.feedback === 'string' ? node.feedback : '';
	});

	function emit() {
		const config: Record<string, unknown> = { ...(node.config ?? {}) };
		if (type === 'choice' || type === 'multi-select') {
			const options = optionsText
				.split('\n')
				.map((s) => s.trim())
				.filter(Boolean)
				.map((label, i) => ({ id: `opt_${i + 1}`, label }));
			config.options = options;
			const ids = correctText
				.split(',')
				.map((s) => s.trim())
				.filter(Boolean);
			// Map by label or id
			const resolved = ids.map((token) => {
				const byId = options.find((o) => o.id === token);
				if (byId) return byId.id;
				const byLabel = options.find((o) => o.label === token);
				return byLabel?.id ?? token;
			});
			config.correct_option_ids = resolved;
		} else if (type === 'fill-blank' || type === 'short-response') {
			config.accepted_answer = accepted;
			config.accepted_answers = accepted
				.split(',')
				.map((s) => s.trim())
				.filter(Boolean);
		} else if (type === 'numeric') {
			config.expected_value = accepted;
		} else if (type === 'match-pairs') {
			config.pairs = pairsText
				.split('\n')
				.map((line) => line.trim())
				.filter(Boolean)
				.map((line) => {
					const [left, ...rest] = line.split('=');
					return { left: (left ?? '').trim(), right: rest.join('=').trim() };
				});
		} else if (type === 'classify') {
			config.categories = categoriesText
				.split('\n')
				.map((s) => s.trim())
				.filter(Boolean);
			config.items = itemsText
				.split('\n')
				.map((s) => s.trim())
				.filter(Boolean);
		} else if (type === 'sequence') {
			config.ordered_items = itemsText
				.split('\n')
				.map((s) => s.trim())
				.filter(Boolean);
			config.items = config.ordered_items;
		}
		onChange?.({
			prompt,
			config,
			feedback: feedback || null
		});
	}
</script>

<div class="ix-editor" data-testid="interaction-editor" data-type={type}>
	<p class="type">{type.replaceAll('-', ' ')}</p>
	<label>
		<span>Prompt</span>
		<textarea bind:value={prompt} rows="2" onblur={emit}></textarea>
	</label>

	{#if type === 'choice' || type === 'multi-select'}
		<label>
			<span>Options <small>one per line</small></span>
			<textarea bind:value={optionsText} rows="4" onblur={emit}></textarea>
		</label>
		<label>
			<span>Correct answer(s) <small>option text or id, comma-separated</small></span>
			<input bind:value={correctText} onblur={emit} />
		</label>
	{:else if type === 'fill-blank' || type === 'short-response' || type === 'numeric'}
		<label>
			<span>{type === 'numeric' ? 'Expected value' : 'Accepted answer'}</span>
			<input bind:value={accepted} onblur={emit} />
		</label>
	{:else if type === 'match-pairs'}
		<label>
			<span>Pairs <small>left = right, one per line</small></span>
			<textarea bind:value={pairsText} rows="4" onblur={emit}></textarea>
		</label>
	{:else if type === 'classify'}
		<label>
			<span>Categories <small>one per line</small></span>
			<textarea bind:value={categoriesText} rows="3" onblur={emit}></textarea>
		</label>
		<label>
			<span>Items <small>one per line</small></span>
			<textarea bind:value={itemsText} rows="3" onblur={emit}></textarea>
		</label>
	{:else if type === 'sequence'}
		<label>
			<span>Ordered items <small>one per line, top = first</small></span>
			<textarea bind:value={itemsText} rows="4" onblur={emit}></textarea>
		</label>
	{/if}

	<label>
		<span>Feedback <small>optional</small></span>
		<input bind:value={feedback} onblur={emit} />
	</label>
</div>

<style>
	.ix-editor {
		display: grid;
		gap: 10px;
		padding: 12px;
		border: 1px solid var(--rule, #ccc);
		border-radius: 10px;
		background: var(--paper, #fff);
	}
	.type {
		margin: 0;
		font-size: 0.75rem;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--ink-3, #888);
	}
	label {
		display: grid;
		gap: 4px;
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--ink-2, #555);
	}
	small {
		font-weight: 400;
		color: var(--ink-3, #888);
	}
	input,
	textarea {
		font: inherit;
		font-weight: 400;
		font-size: 0.875rem;
		padding: 8px 10px;
		border: 1px solid var(--rule, #ccc);
		border-radius: 8px;
		background: var(--surface, #fff);
		color: var(--ink, #111);
	}
</style>
