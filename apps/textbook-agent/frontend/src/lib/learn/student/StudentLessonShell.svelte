<script lang="ts">
	import { isLearnDocument, type LearnDocument } from '$lib/learn/document/types';
	import OrderedDocumentList from './OrderedDocumentList.svelte';
	import type { AttemptSubmitHandler } from '$lib/learn/interactions/types';
	import type { StoredAttempt } from './api/attempts';

	interface Props {
		document: LearnDocument;
		/** Unused for v2 flat documents; kept for call-site compatibility. */
		activeIndex?: number;
		onActiveIndexChange?: (index: number) => void;
		/** Preview mode: same shell/interactions, never posts attempts. */
		preview?: boolean;
		attemptsByInteraction?: Map<string, StoredAttempt>;
		onSubmitAttempt?: AttemptSubmitHandler;
	}

	let {
		document,
		preview = false,
		attemptsByInteraction = new Map(),
		onSubmitAttempt = undefined
	}: Props = $props();

	const isV2 = $derived(isLearnDocument(document));
</script>

<div
	class="student-lesson-shell"
	data-testid="student-lesson-shell"
	data-preview={preview ? 'true' : 'false'}
	data-persist-attempts={preview ? 'false' : 'true'}
	data-render-mode="ordered-nodes"
	data-document-version="2"
>
	<header class="shell-header">
		<p class="eyebrow">Learn</p>
		<h1>{document.title}</h1>
		<p class="lede">{document.subject} · {document.nodes.length} nodes</p>
	</header>

	{#if isV2}
		<section class="stage-panel" data-testid="stage-panel" data-document-version="2">
			<article class="stage-article">
				<p class="stage-badge">document · v2</p>
				<OrderedDocumentList
					{document}
					{preview}
					{attemptsByInteraction}
					{onSubmitAttempt}
				/>
			</article>
		</section>
	{:else}
		<p class="empty">
			This release uses a retired LessonDocument v1 payload. Republish as LearnDocument v2 to open
			it here.
		</p>
	{/if}
</div>

<style>
	.student-lesson-shell {
		display: grid;
		gap: 18px;
		max-width: 1080px;
		margin: 0 auto;
		padding: 24px 18px 48px;
		color: var(--ink);
		background: var(--paper);
	}
	.shell-header .eyebrow,
	.stage-badge {
		margin: 0 0 6px;
		color: var(--ink-3);
		font: 500 11px 'IBM Plex Mono', monospace;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}
	.shell-header h1 {
		margin: 0;
		font: 500 34px/1.1 Fraunces, Georgia, serif;
		letter-spacing: -0.03em;
	}
	.lede,
	.empty {
		color: var(--ink-2);
		font-size: 14px;
		line-height: 1.6;
	}
	.stage-panel {
		border: 1px solid var(--rule);
		border-radius: 14px;
		background: var(--surface);
		padding: 18px;
	}
	.stage-article {
		display: grid;
		gap: 12px;
	}
	@media (max-width: 720px) {
		.shell-header h1 {
			font-size: 28px;
		}
	}
</style>
