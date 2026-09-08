<script lang="ts">
	import {
		LectioThemeSurface,
		basePresetMap,
		type LessonDocument
	} from '@lectio/learn';
	import { buildStudentStages, clampStageIndex } from './student-shell';
	import StudentStageNav from './StudentStageNav.svelte';
	import OrderedBlockList from './OrderedBlockList.svelte';
	import type { AttemptSubmitHandler } from './OrderedBlockList.svelte';
	import type { StoredAttempt } from './api/attempts';

	interface Props {
		document: LessonDocument;
		activeIndex?: number;
		onActiveIndexChange?: (index: number) => void;
		/** Preview mode: same shell/interactions, never posts attempts. */
		preview?: boolean;
		attemptsByInteraction?: Map<string, StoredAttempt>;
		onSubmitAttempt?: AttemptSubmitHandler;
	}

	let {
		document,
		activeIndex = undefined,
		onActiveIndexChange = undefined,
		preview = false,
		attemptsByInteraction = new Map(),
		onSubmitAttempt = undefined
	}: Props = $props();

	const stages = $derived(buildStudentStages(document));
	let internalIndex = $state(0);
	const currentIndex = $derived(clampStageIndex(activeIndex ?? internalIndex, stages.length));
	const activeStage = $derived(stages[currentIndex] ?? null);
	const preset = $derived(basePresetMap[document.preset_id] ?? null);

	function selectStage(index: number) {
		const next = clampStageIndex(index, stages.length);
		if (activeIndex === undefined) internalIndex = next;
		onActiveIndexChange?.(next);
	}
</script>

<div
	class="student-lesson-shell"
	data-testid="student-lesson-shell"
	data-preview={preview ? 'true' : 'false'}
	data-persist-attempts={preview ? 'false' : 'true'}
	data-render-mode="ordered-blocks"
>
	<header class="shell-header">
		<p class="eyebrow">{preset?.name ?? document.preset_id}</p>
		<h1>{document.title}</h1>
		<p class="lede">{document.subject} · {stages.length} stages</p>
	</header>

	{#if stages.length === 0}
		<p class="empty">This lesson has no sections yet.</p>
	{:else}
		<StudentStageNav {stages} {currentIndex} onSelect={selectStage} />

		<section class="stage-panel" data-testid="stage-panel" data-section-id={activeStage?.section.id}>
			{#if activeStage}
				<LectioThemeSurface {preset}>
					<article class="stage-article">
						<p class="stage-badge">
							{activeStage.assessment_mode}
							{#if activeStage.required}
								· required
							{/if}
						</p>
						<!-- Authoritative block_ids order — not SectionContent reconstruction. -->
						<OrderedBlockList
							{document}
							sectionId={activeStage.section.id}
							{preview}
							{attemptsByInteraction}
							{onSubmitAttempt}
						/>
					</article>
				</LectioThemeSurface>
			{:else}
				<p class="empty">Section content could not be resolved.</p>
			{/if}
		</section>
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
