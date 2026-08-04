<script lang="ts">
	import { LectioThemeSurface, basePresetMap, templateRegistryMap, usePrintMode } from 'lectio';
	import { buildSectionSlots, type ViewerSectionSlot } from '$lib/generation/viewer-state';
	import PrintSectionLink from '$lib/components/PrintSectionLink.svelte';
	import type { GenerationDocument } from '$lib/types';

	interface Props {
		document: GenerationDocument;
		sectionSlots?: ViewerSectionSlot[];
		/** When set and `document.status === 'completed'`, shows "Open in Builder" in the lesson header. */
		onExportForBuilder?: () => void;
	}

	let { document, sectionSlots = undefined, onExportForBuilder = undefined }: Props = $props();

	const showExportForBuilder = $derived(
		document.status === 'completed' && typeof onExportForBuilder === 'function'
	);

	const template = $derived(templateRegistryMap[document.template_id]);
	const preset = $derived(basePresetMap[document.preset_id] ?? null);
	const resolvedSectionSlots = $derived(
		sectionSlots ?? buildSectionSlots(document, document.section_manifest.length || document.sections.length)
	);
	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());

	function sectionForSlot(slot: ViewerSectionSlot) {
		return slot.section ?? slot.partial?.content ?? null;
	}
</script>

{#if template}
	<LectioThemeSurface {preset}>
		<div class="page-frame space-y-6 textbook-document-shell" data-print-mode={printMode ? 'true' : 'false'}>
			{#if !printMode}
				<header class="lesson-shell p-6 sm:p-8">
					<div class="relative z-10 flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
						<div class="space-y-3">
							<p class="eyebrow">{preset?.name ?? document.preset_id}</p>
							<h2 class="text-3xl font-serif text-primary sm:text-4xl">{document.subject}</h2>
							<p class="max-w-3xl text-base leading-7 text-muted-foreground sm:text-lg sm:leading-8">
								{document.context}
							</p>
						</div>

						<div class="lesson-header-actions">
							{#if showExportForBuilder}
								<button
									type="button"
									class="export-builder-btn"
									onclick={() => onExportForBuilder?.()}
								>
									Open in Builder
								</button>
							{/if}
							<div class="document-meta">
								<span>{template.contract.name}</span>
								<span>{resolvedSectionSlots.length} sections</span>
							</div>
						</div>
					</div>
				</header>
			{/if}

			<div class="section-stack" data-print-mode={printMode ? 'true' : 'false'}>
				{#each resolvedSectionSlots as slot (slot.section_id)}
					{@const renderableSection = sectionForSlot(slot)}
					{#if slot.status === 'ready' && slot.section}
						{@const TemplateRender = template.render}
						<article class="animate-step-reveal" id={`section-${slot.section_id}`}>
							<TemplateRender section={slot.section} />
						</article>
						{#if printMode}
							<PrintSectionLink generationId={document.generation_id} section={slot.section} />
						{/if}
					{:else if renderableSection}
						{@const TemplateRender = template.render}
						<article class="animate-step-reveal section-partial" id={`section-${slot.section_id}`} data-section-status={slot.status}>
							<div class="section-partial-badge">Section {slot.position} {slot.status.replaceAll('_', ' ')}</div>
							<TemplateRender section={renderableSection} />
						</article>
					{:else}
						<article class="glass-panel section-skeleton" aria-busy="true">
							<p class="skeleton-kicker">Generating section {slot.position}</p>
							<h3 class="skeleton-title">{slot.title}</h3>
							<div class="skeleton-line short"></div>
							<div class="skeleton-line"></div>
							<div class="skeleton-line"></div>
						</article>
					{/if}
				{/each}
			</div>
		</div>
	</LectioThemeSurface>
{:else}
	<p>Unknown Lectio template: {document.template_id}</p>
{/if}

<style>
	.lesson-header-actions {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--rh-gap-component-tight, 0.75rem);
	}

	@media (min-width: 1024px) {
		.lesson-header-actions {
			align-items: flex-end;
		}
	}

	.export-builder-btn {
		flex-shrink: 0;
		padding: var(--space-2, 0.5rem) var(--space-4, 1rem);
		font-size: 0.9rem;
		font-weight: 600;
		color: #0f172a;
		background: #e2e8f0;
		border: 1px solid #cbd5e1;
		border-radius: var(--rh-radius-inner, 0.375rem);
		cursor: pointer;
	}

	.export-builder-btn:hover {
		background: #cbd5e1;
	}

	.document-meta {
		display: grid;
		gap: var(--space-2, 0.55rem);
		align-content: start;
		justify-items: start;
	}

	.document-meta span {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: var(--space-2, 0.45rem) var(--space-3, 0.75rem);
		border-radius: 999px;
		border: 1px solid color-mix(in srgb, var(--border) 72%, transparent);
		background: color-mix(in srgb, var(--secondary) 78%, white 22%);
		color: color-mix(in srgb, var(--foreground) 82%, white 18%);
		font-size: 0.82rem;
		font-weight: 600;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.section-stack {
		display: grid;
		gap: var(--rh-gap-section, 1.25rem);
	}

	.section-skeleton {
		display: grid;
		gap: var(--rh-gap-component, 0.8rem);
		padding: var(--rh-pad-card-tight, 1.25rem);
		border-radius: var(--rh-radius-outer, 1.5rem);
	}

	.section-partial {
		display: grid;
		gap: var(--rh-gap-component, 0.85rem);
	}

	.section-partial-badge {
		display: inline-flex;
		align-items: center;
		width: fit-content;
		padding: var(--space-1, 0.28rem) var(--space-3, 0.65rem);
		border-radius: 999px;
		background: color-mix(in srgb, var(--secondary) 76%, white 24%);
		color: color-mix(in srgb, var(--foreground) 82%, white 18%);
		font-size: 0.74rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.skeleton-kicker {
		margin: 0;
		font-size: var(--rh-eyebrow-size, 0.78rem);
		letter-spacing: var(--rh-eyebrow-tracking, 0.12em);
		text-transform: uppercase;
		color: var(--accent);
	}

	.skeleton-title {
		margin: 0;
		font-size: 1.2rem;
		color: var(--foreground);
	}

	.skeleton-line {
		height: 0.8rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--secondary) 82%, white 18%);
	}

	.skeleton-line.short {
		width: 68%;
	}

	@media (min-width: 1024px) {
		.document-meta {
			justify-items: end;
		}
	}

	@media print {
		.textbook-document-shell[data-print-mode='true'] {
			padding: 0;
		}
	}
</style>
