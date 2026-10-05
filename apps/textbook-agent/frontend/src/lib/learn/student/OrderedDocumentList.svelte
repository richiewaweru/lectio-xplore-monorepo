<script lang="ts">
	import DocumentCanvas from '$lib/learn/document/DocumentCanvas.svelte';
	import InlineMarkup from '$lib/learn/document/renderers/InlineMarkup.svelte';
	import type { InteractionAttemptState, LearnDocument, LearnSection } from '$lib/learn/document/types';
	import type { AttemptSubmitHandler, ServerEvaluation } from '$lib/learn/interactions/types';
	import type { StoredAttempt } from './api/attempts';
	import SectionHeader from './SectionHeader.svelte';

	interface Props {
		document: LearnDocument;
		selectedNodeId?: string | null;
		onSelectNode?: (nodeId: string) => void;
		onSectionChange?: (sectionId: string) => void | Promise<void>;
		attemptsByInteraction?: Map<string, InteractionAttemptState | StoredAttempt>;
		preview?: boolean;
		onSubmitAttempt?: AttemptSubmitHandler;
	}

	let {
		document,
		selectedNodeId = null,
		onSelectNode = undefined,
		onSectionChange = undefined,
		attemptsByInteraction = new Map(),
		preview = false,
		onSubmitAttempt = undefined
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

	let activeSectionId = $state<string>('all');
	const sections = $derived(document.sections ?? []);

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

	function renderSection(section: LearnSection, index: number) {
		return sectionDocument(section);
	}

	function interactionCountBefore(index: number): number {
		return sections.slice(0, index).reduce(
			(total, section) => total + sectionDocument(section).nodes.filter((node) => node.kind === 'interaction').length,
			0
		);
	}
</script>

<div class="ordered-document-list" data-testid="ordered-document-list" data-preview={preview ? 'true' : 'false'}>
	{#if sections.length > 0}
		<nav class="lesson-map" data-testid="runtime-section-tabs" aria-label="Lesson sections">
			<button type="button" class="all-sections" class:active={activeSectionId === 'all'} onclick={() => selectSection('all')}>
				All sections
			</button>
			<ol>
				{#each sections as section, index}
					<li>
						<button type="button" class:active={activeSectionId === section.id} aria-current={activeSectionId === section.id ? 'page' : undefined} onclick={() => selectSection(section.id)}>
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
					<section class="lesson-section" aria-labelledby={`section-heading-${index + 1}`}>
						<SectionHeader title={section.title ?? `Part ${index + 1}`} index={index + 1} total={sections.length} />
						<div id={`section-heading-${index + 1}`} class="section-content">
							<DocumentCanvas document={renderSection(section, index)} {interactionOffset} attemptsByInteraction={attemptStates} onSubmitInteraction={preview || !onSubmitAttempt ? undefined : onSubmitInteraction} />
						</div>
					</section>
				{/each}
			</div>
		{:else}
			{@const selected = sections.find((section) => section.id === activeSectionId)}
			{#if selected}
				{@const selectedIndex = sections.indexOf(selected)}
				{@const interactionOffset = interactionCountBefore(selectedIndex)}
				<section class="lesson-section single-section" aria-labelledby={`section-heading-${selectedIndex + 1}`}>
					<SectionHeader title={selected.title ?? `Part ${selectedIndex + 1}`} index={selectedIndex + 1} total={sections.length} />
					<div id={`section-heading-${selectedIndex + 1}`} class="section-content">
						<DocumentCanvas document={renderSection(selected, selectedIndex)} {interactionOffset} attemptsByInteraction={attemptStates} onSubmitInteraction={preview || !onSubmitAttempt ? undefined : onSubmitInteraction} />
					</div>
				</section>
			{/if}
		{/if}
	{:else}
		<DocumentCanvas document={document} attemptsByInteraction={attemptStates} onSubmitInteraction={preview || !onSubmitAttempt ? undefined : onSubmitInteraction} />
	{/if}
</div>

<style>
	.ordered-document-list { display: grid; gap: 36px; min-width: 0; }
	.lesson-map { display: grid; gap: 14px; }
	.lesson-map ol { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; list-style: none; margin: 0; padding: 0; }
	.lesson-map li { min-width: 0; }
	.lesson-map button { width: 100%; min-height: 56px; border: 1px solid var(--rule, #ddd8cc); border-radius: 12px; background: var(--surface, #fff); color: var(--ink, #1c2321); padding: 11px 12px; cursor: pointer; font: inherit; text-align: left; }
	.lesson-map button:hover, .lesson-map button:focus-visible { border-color: var(--ink, #1c2321); }
	.lesson-map button.active { border-color: var(--ink, #1c2321); box-shadow: inset 0 -3px 0 var(--ink, #1c2321); }
	.lesson-map .all-sections { justify-self: start; width: auto; min-height: auto; border: 0; background: transparent; padding: 0; color: var(--muted, #5b6460); font-size: 14px; font-weight: 700; }
	.lesson-map .all-sections.active { box-shadow: none; color: var(--ink, #1c2321); }
	.lesson-map li button { display: grid; grid-template-columns: 28px minmax(0, 1fr); align-items: center; gap: 9px; }
	.lesson-map li button > span:last-child { min-width: 0; overflow-wrap: anywhere; line-height: 1.3; }
	.map-number { display: grid; place-items: center; width: 26px; height: 26px; border-radius: 50%; background: var(--sand, #f3eee3); color: var(--ink, #1c2321); font-weight: 700; }
	.lesson-map li button.active .map-number { background: var(--ink, #1c2321); color: var(--surface, #fff); }
	.lesson-sections { display: grid; gap: 72px; }
	.lesson-section { display: grid; gap: 22px; min-width: 0; scroll-margin-top: 20px; }
	.section-content { min-width: 0; }
	@media (max-width: 720px) {
		.lesson-map ol { grid-template-columns: repeat(2, minmax(0, 1fr)); }
		.lesson-sections { gap: 54px; }
	}
	@media (max-width: 420px) {
		.lesson-map ol { grid-template-columns: 1fr; }
	}
</style>
