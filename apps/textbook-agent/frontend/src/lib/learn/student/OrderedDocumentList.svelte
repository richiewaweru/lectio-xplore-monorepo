<script lang="ts">
	import { untrack } from 'svelte';
	import DocumentCanvas from '$lib/learn/document/DocumentCanvas.svelte';
	import InlineMarkup from '$lib/learn/document/renderers/InlineMarkup.svelte';
	import type { InteractionAttemptState, LearnDocument, LearnSection } from '$lib/learn/document/types';
	import type { AttemptSubmitHandler, ServerEvaluation } from '$lib/learn/interactions/types';
	import type { StoredAttempt } from './api/attempts';
	import SectionHeader from './SectionHeader.svelte';
	import type { NextLessonInfo } from './instance-topic';

	interface Props {
		document: LearnDocument;
		selectedNodeId?: string | null;
		onSelectNode?: (nodeId: string) => void;
		onSectionChange?: (sectionId: string) => void | Promise<void>;
		attemptsByInteraction?: Map<string, InteractionAttemptState | StoredAttempt>;
		preview?: boolean;
		onSubmitAttempt?: AttemptSubmitHandler;
		/** Section ids already completed (learner view): resume after the last one. */
		initialCompletedSectionIds?: string[];
		initialCurrentSectionId?: string | null;
		/** The lesson that follows this one on the topic path (null/undefined: none). */
		nextLesson?: NextLessonInfo | null;
		/** Called by "Finish lesson" on the last section when there is no next lesson. */
		onFinish?: () => void | Promise<void>;
		/** Fired when the learner follows the "next lesson is ready" link (completes this lesson). */
		onLeaveForNextLesson?: () => void | Promise<void>;
	}

	let {
		document,
		selectedNodeId = null,
		onSelectNode = undefined,
		onSectionChange = undefined,
		attemptsByInteraction = new Map(),
		preview = false,
		onSubmitAttempt = undefined,
		initialCompletedSectionIds = [],
		initialCurrentSectionId = null,
		nextLesson = null,
		onFinish = undefined,
		onLeaveForNextLesson = undefined
	}: Props = $props();

	const attemptStates = $derived.by(() => {
		const map = new Map<string, InteractionAttemptState>();
		for (const [id, attempt] of attemptsByInteraction.entries()) {
			if ('interactionId' in attempt) {
				map.set(id, attempt as InteractionAttemptState);
				continue;
			}
			const stored = attempt as StoredAttempt;
			map.set(id, {
				interactionId: stored.interaction_id,
				outcome: stored.outcome,
				feedback: stored.outcome,
				response: stored.response_json,
				score_earned: stored.score_earned,
				score_possible: stored.score_possible
			});
		}
		return map;
	});

	const sections = $derived(document.sections ?? []);

	// Learners see one section at a time; teacher preview keeps the "All sections" view.
	function startIndex(): number {
		const list = document.sections ?? [];
		if (list.length === 0) return 0;
		const done = new Set(initialCompletedSectionIds);
		let lastDone = -1;
		list.forEach((section, i) => {
			if (done.has(section.id)) lastDone = i;
		});
		if (lastDone >= 0) return Math.min(lastDone + 1, list.length - 1);
		const current = list.findIndex((section) => section.id === initialCurrentSectionId);
		return current >= 0 ? current : 0;
	}

	let activeSectionId = $state<string>(
		untrack(() => (preview ? 'all' : (document.sections?.[startIndex()]?.id ?? 'all')))
	);
	let reachedIndex = $state(untrack(() => (preview ? 0 : startIndex())));
	let finishing = $state(false);
	let rootEl = $state<HTMLElement | null>(null);

	const activeIndex = $derived(sections.findIndex((section) => section.id === activeSectionId));
	const isLast = $derived(activeIndex >= 0 && activeIndex === sections.length - 1);

	function sectionDocument(section: LearnSection): LearnDocument {
		const allowed = new Set(section.node_ids ?? []);
		return { ...document, nodes: document.nodes.filter((node) => allowed.has(node.id)) };
	}

	async function onSubmitInteraction(args: {
		interactionId: string;
		response: Record<string, unknown>;
	}): Promise<ServerEvaluation> {
		if (preview || !onSubmitAttempt) throw new Error('Preview mode — attempts are not persisted');
		return onSubmitAttempt({ interactionId: args.interactionId, response: args.response });
	}

	function selectSection(sectionId: string) {
		activeSectionId = sectionId;
		void onSectionChange?.(sectionId);
	}

	function scrollToTop() {
		if (typeof rootEl?.scrollIntoView === 'function') rootEl.scrollIntoView({ block: 'start' });
	}

	function jumpTo(index: number) {
		if (index < 0 || index > reachedIndex) return;
		activeSectionId = sections[index].id;
		scrollToTop();
	}

	function goPrevious() {
		jumpTo(activeIndex - 1);
	}

	function goNext() {
		if (activeIndex < 0 || activeIndex >= sections.length - 1) return;
		void onSectionChange?.(sections[activeIndex].id); // leaving a section marks it visited
		const next = activeIndex + 1;
		reachedIndex = Math.max(reachedIndex, next);
		activeSectionId = sections[next].id;
		scrollToTop();
	}

	async function finish() {
		if (finishing || activeIndex < 0) return;
		finishing = true;
		try {
			await onSectionChange?.(sections[activeIndex].id);
			await onFinish?.();
		} finally {
			finishing = false;
		}
	}

	function renderSection(section: LearnSection, index: number) {
		return sectionDocument(section);
	}

	function figureCountBefore(index: number): number {
		return sections.slice(0, index).reduce(
			(total, section) => total + sectionDocument(section).nodes.filter((node) => node.kind === 'figure').length,
			0
		);
	}

	function interactionCountBefore(index: number): number {
		return sections.slice(0, index).reduce(
			(total, section) => total + sectionDocument(section).nodes.filter((node) => node.kind === 'interaction').length,
			0
		);
	}
</script>

<div class="ordered-document-list" bind:this={rootEl} data-testid="ordered-document-list" data-preview={preview ? 'true' : 'false'}>
	{#if sections.length > 0}
		<nav class="lesson-map" data-testid="runtime-section-tabs" aria-label="Lesson sections">
			{#if preview}
				<button type="button" class="all-sections" class:active={activeSectionId === 'all'} onclick={() => selectSection('all')}>
					All sections
				</button>
			{/if}
			<ol>
				{#each sections as section, index}
					<li>
						<button type="button" class:active={activeSectionId === section.id} class:ahead={!preview && index > reachedIndex} disabled={!preview && index > reachedIndex} aria-current={activeSectionId === section.id ? 'page' : undefined} onclick={() => (preview ? selectSection(section.id) : jumpTo(index))}>
							<span class="map-number">{index + 1}</span>
							<span><InlineMarkup value={section.title ?? `Part ${index + 1}`} /></span>
						</button>
					</li>
				{/each}
			</ol>
		</nav>

		{#if activeSectionId === 'all'}
			<div class="lesson-sections">
				{#each sections as section, index (section.id)}
					{@const interactionOffset = interactionCountBefore(index)}
					{@const figureOffset = figureCountBefore(index)}
					<section class="lesson-section" aria-labelledby={`section-heading-${index + 1}`}>
						<SectionHeader title={section.title ?? `Part ${index + 1}`} index={index + 1} total={sections.length} />
						<div id={`section-heading-${index + 1}`} class="section-content">
							<DocumentCanvas document={renderSection(section, index)} {interactionOffset} {figureOffset} attemptsByInteraction={attemptStates} onSubmitInteraction={preview || !onSubmitAttempt ? undefined : onSubmitInteraction} />
						</div>
					</section>
				{/each}
			</div>
		{:else}
			{@const selected = sections.find((section) => section.id === activeSectionId)}
			{#if selected}
				{@const selectedIndex = sections.indexOf(selected)}
				{@const interactionOffset = interactionCountBefore(selectedIndex)}
					{@const figureOffset = figureCountBefore(selectedIndex)}
				<section class="lesson-section single-section" aria-labelledby={`section-heading-${selectedIndex + 1}`}>
					<SectionHeader title={selected.title ?? `Part ${selectedIndex + 1}`} index={selectedIndex + 1} total={sections.length} />
					<div id={`section-heading-${selectedIndex + 1}`} class="section-content">
						<DocumentCanvas document={renderSection(selected, selectedIndex)} {interactionOffset} {figureOffset} attemptsByInteraction={attemptStates} onSubmitInteraction={preview || !onSubmitAttempt ? undefined : onSubmitInteraction} />
					</div>
				</section>
				{#if !preview}
					<nav class="section-nav" data-testid="section-nav" aria-label="Section navigation">
						{#if selectedIndex > 0}
							<button type="button" class="nav-button prev" data-testid="section-prev" onclick={goPrevious}>&larr; Previous</button>
						{:else}
							<span></span>
						{/if}
						{#if !isLast}
							<button type="button" class="nav-button next" data-testid="section-next" onclick={goNext}>Next &rarr;</button>
						{:else if nextLesson?.state === 'ready' && nextLesson.instance_id}
							<a class="nav-button next lesson-card" data-testid="next-lesson-ready" href={`/learn/instances/${nextLesson.instance_id}`} onclick={() => void onLeaveForNextLesson?.()}>{nextLesson.number ? `Lesson ${nextLesson.number}` : 'Next lesson'} is ready &rarr;</a>
						{:else if nextLesson?.state === 'pending'}
							<p class="lesson-card pending" data-testid="next-lesson-pending">{nextLesson.number ? `Lesson ${nextLesson.number}` : 'The next lesson'} is being prepared</p>
						{:else}
							<button type="button" class="nav-button next" data-testid="finish-lesson" disabled={finishing} onclick={() => void finish()}>{finishing ? 'Finishing…' : 'Finish lesson'}</button>
						{/if}
					</nav>
				{/if}
			{/if}
		{/if}
	{:else}
		<DocumentCanvas document={document} attemptsByInteraction={attemptStates} onSubmitInteraction={preview || !onSubmitAttempt ? undefined : onSubmitInteraction} />
	{/if}
</div>

<style>
	.ordered-document-list { display: grid; gap: 36px; min-width: 0; }
	.lesson-map { display: grid; gap: 14px; }
	.lesson-map ol { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 190px), 1fr)); gap: 10px; list-style: none; margin: 0; padding: 0; }
	.lesson-map li { min-width: 0; }
	.lesson-map button { width: 100%; height: 100%; min-height: 56px; border: 1px solid var(--rule, #ddd8cc); border-radius: 12px; background: var(--surface, #fff); color: var(--ink, #1c2321); padding: 11px 12px; cursor: pointer; font: inherit; text-align: left; }
	.lesson-map button:hover, .lesson-map button:focus-visible { border-color: var(--ink, #1c2321); }
	.lesson-map button.active { border-color: var(--ink, #1c2321); box-shadow: inset 0 -3px 0 var(--ink, #1c2321); }
	.lesson-map .all-sections { justify-self: start; width: auto; min-height: auto; border: 0; background: transparent; padding: 0; color: var(--muted, #5b6460); font-size: 14px; font-weight: 700; }
	.lesson-map .all-sections.active { box-shadow: none; color: var(--ink, #1c2321); }
	.lesson-map li button { display: grid; grid-template-columns: 28px minmax(0, 1fr); align-items: center; gap: 9px; }
	.lesson-map li button > span:last-child { min-width: 0; overflow-wrap: break-word; line-height: 1.3; }
	.map-number { display: grid; place-items: center; width: 26px; height: 26px; border-radius: 50%; background: var(--sand, #f3eee3); color: var(--ink, #1c2321); font-weight: 700; }
	.lesson-map li button.active .map-number { background: var(--ink, #1c2321); color: var(--surface, #fff); }
	.lesson-map li button:disabled { cursor: not-allowed; opacity: 0.5; }
	.section-nav { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; }
	.nav-button { display: inline-flex; align-items: center; justify-content: center; min-height: 48px; padding: 10px 20px; border: 1px solid var(--ink, #1c2321); border-radius: 999px; background: var(--surface, #fff); color: var(--ink, #1c2321); font: inherit; font-weight: 700; text-decoration: none; cursor: pointer; }
	.nav-button.next { background: var(--ink, #1c2321); color: var(--surface, #fff); margin-left: auto; }
	.nav-button:disabled { opacity: 0.6; cursor: wait; }
	.lesson-card.pending { margin: 0 0 0 auto; padding: 10px 4px; color: var(--muted, #5b6460); font-weight: 700; }
	.lesson-sections { display: grid; gap: 72px; }
	.lesson-section { display: grid; gap: 22px; min-width: 0; scroll-margin-top: 20px; }
	.section-content { min-width: 0; }
	@media (max-width: 720px) {
		.lesson-sections { gap: 54px; }
	}
</style>
