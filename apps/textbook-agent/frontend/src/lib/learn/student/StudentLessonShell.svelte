<script lang="ts">
	import { isLearnDocument, type LearnDocument } from '$lib/learn/document/types';
	import OrderedDocumentList from './OrderedDocumentList.svelte';
	import type { AttemptSubmitHandler } from '$lib/learn/interactions/types';
	import type { StoredAttempt } from './api/attempts';
	import InlineMarkup from '$lib/learn/document/renderers/InlineMarkup.svelte';

	interface Props {
		document: LearnDocument;
		activeIndex?: number;
		onActiveIndexChange?: (index: number) => void;
		onSectionChange?: (sectionId: string) => void | Promise<void>;
		preview?: boolean;
		attemptsByInteraction?: Map<string, StoredAttempt>;
		onSubmitAttempt?: AttemptSubmitHandler;
	}

	let {
		document,
		preview = false,
		attemptsByInteraction = new Map(),
		onSubmitAttempt = undefined,
		onSectionChange = undefined
	}: Props = $props();

	const isV2 = $derived(isLearnDocument(document));
	const subjectLine = $derived(document.subject?.trim() || '');
</script>

<svelte:head>
	<link rel="preconnect" href="https://fonts.googleapis.com" />
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
	<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet" />
</svelte:head>

<div class="student-lesson-shell" data-testid="student-lesson-shell" data-preview={preview ? 'true' : 'false'}>
	<header class="lesson-header">
		<p class="subject-line">{subjectLine}</p>
		<h1><InlineMarkup value={document.title} /></h1>
	</header>

	{#if isV2}
		<main class="stage-article">
			<OrderedDocumentList
				{document}
				{preview}
				{attemptsByInteraction}
				{onSubmitAttempt}
				onSectionChange={preview ? undefined : onSectionChange}
			/>
		</main>
	{:else}
		<p class="empty">This lesson is not available yet.</p>
	{/if}
</div>

<style>
	.student-lesson-shell {
		--ground: #faf8f3;
		--ink: #1c2321;
		--muted: #5b6460;
		--rule: #ddd8cc;
		--rule-strong: #c9c3b5;
		--surface: #ffffff;
		--sand: #f3eee3;
		--green: #1b5e40;
		--green-tint: #e4f0e8;
		--action: #c2410c;
		--paper: var(--ground);
		--font-sans: 'Atkinson Hyperlegible', ui-sans-serif, system-ui, sans-serif;
		--font-serif: Fraunces, ui-serif, Georgia, serif;
		box-sizing: border-box;
		min-height: 100vh;
		padding: 56px 24px 88px;
		background: var(--ground);
		color: var(--ink);
		font-family: var(--font-sans);
	}
	.lesson-header,
	.stage-article { width: min(720px, 100%); margin-inline: auto; }
	.lesson-header { margin-bottom: 42px; }
	.subject-line { margin: 0 0 13px; color: var(--muted); font-size: 14px; font-weight: 700; letter-spacing: .08em; }
	.lesson-header h1 { margin: 0; color: var(--ink); font: 600 46px/1.08 var(--font-serif); letter-spacing: -.035em; text-wrap: balance; }
	.stage-article { min-width: 0; }
	.empty { width: min(720px, 100%); margin: 0 auto; color: var(--muted); font-size: 18px; }
	@media (max-width: 720px) {
		.student-lesson-shell { padding: 32px 24px 56px; }
		.lesson-header { margin-bottom: 32px; }
		.lesson-header h1 { font-size: 38px; }
	}
	@media (max-width: 420px) {
		.student-lesson-shell { padding-inline: 20px; }
		.lesson-header h1 { font-size: 34px; }
	}
</style>
