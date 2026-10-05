<script lang="ts">
	import type { CalloutNode } from '../types';
	import InlineMarkup from './InlineMarkup.svelte';

	interface Props { node: CalloutNode; }
	let { node }: Props = $props();
	const tone = $derived(node.tone ?? 'note');
	const structuredMisconception = $derived(
		node.variant === 'misconception' && Boolean(node.belief && node.evidence && node.conclusion)
	);
	const label = $derived(
		node.variant === 'key_idea'
			? 'Key idea'
			: node.title || (node.variant === 'note' ? 'Note' : tone === 'warning' ? 'Common belief' : tone)
	);
</script>

{#if structuredMisconception}
	<div class="misconception-wrap">
		<aside class="learn-callout misconception" data-testid="callout-node" data-variant="misconception">
			<header><span><InlineMarkup value={label} /></span></header>
			<div class="misconception-row belief-row">
				<strong>The belief</strong>
				<p>{#if /^\s*[\"“]/.test(node.belief ?? '')}<InlineMarkup value={node.belief} />{:else}“<InlineMarkup value={node.belief} />”{/if}</p>
			</div>
			<div class="misconception-row">
				<strong>The evidence</strong>
				<p><InlineMarkup value={node.evidence} /></p>
			</div>
			<div class="misconception-row so-row">
				<strong>So</strong>
				<p><InlineMarkup value={node.conclusion} /></p>
			</div>
		</aside>
		{#if node.aside}<p class="aside"><InlineMarkup value={node.aside} /></p>{/if}
	</div>
{:else}
	<aside
		class="learn-callout"
		class:key-idea={node.variant === 'key_idea'}
		class:note={node.variant === 'note'}
		data-testid="callout-node"
		data-tone={tone}
		data-variant={node.variant ?? 'legacy'}
	>
		<p class="title"><InlineMarkup value={label} /></p>
		<p class="body"><InlineMarkup value={node.body ?? ''} /></p>
	</aside>
{/if}

<style>
	.learn-callout { margin: 0; padding: 22px 24px; border: 1px solid var(--rule, #ddd8cc); border-radius: 14px; background: var(--sand, #f3eee3); display: grid; gap: 10px; }
	.learn-callout.key-idea { border-color: transparent; background: var(--green-tint, #e4f0e8); }
	.learn-callout.key-idea .body { font: 700 22px/1.35 var(--font-sans, 'Atkinson Hyperlegible', sans-serif); }
	.learn-callout.note { background: var(--sand, #f3eee3); }
	.title, .learn-callout header { margin: 0; font-size: 14px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted, #5b6460); }
	.learn-callout.key-idea .title { color: var(--green, #1b5e40); }
	.body, .misconception-row p, .aside { margin: 0; font-size: 18px; line-height: 1.6; color: var(--ink, #1c2321); }
	.misconception { padding: 0; gap: 0; background: var(--surface, #fff); overflow: hidden; }
	.misconception header { padding: 13px 18px; background: var(--sand, #f3eee3); color: var(--ink, #1c2321); }
	.misconception-row { display: grid; grid-template-columns: 150px 1fr; gap: 18px; padding: 17px 18px; border-top: 1px solid var(--rule, #ddd8cc); }
	.misconception-row strong { color: var(--muted, #5b6460); font-size: 14px; text-transform: uppercase; letter-spacing: 0.08em; }
	.belief-row p { font-style: italic; }
	.so-row strong { color: var(--green, #1b5e40); }
	.aside { margin: 10px 2px 0; padding: 0 4px; }
	@media (max-width: 600px) { .misconception-row { grid-template-columns: 1fr; gap: 6px; } }
</style>
