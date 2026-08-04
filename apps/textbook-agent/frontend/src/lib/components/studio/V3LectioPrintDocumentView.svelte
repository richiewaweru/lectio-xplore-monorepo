<script lang="ts">
	// Production PDF content shell: Lectio template render only (no stream/slots).
	import { LectioThemeSurface, basePresetMap, templateRegistryMap, usePrintMode } from 'lectio';
	import type { GenerationDocument } from '$lib/types';

	let { document }: { document: GenerationDocument } = $props();

	const template = $derived(templateRegistryMap[document.template_id]);
	const preset = $derived(basePresetMap[document.preset_id] ?? basePresetMap['blue-classroom'] ?? null);
	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());
</script>

{#if template}
	<LectioThemeSurface {preset}>
		<div class="page-frame textbook-document-shell" data-print-mode={printMode ? 'true' : 'false'}>
			<div class="section-stack" data-print-mode={printMode ? 'true' : 'false'}>
				{#each document.sections as section (section.section_id)}
					{@const TemplateRender = template.render}
					<article id={`section-${section.section_id}`}>
						<TemplateRender {section} />
					</article>
				{/each}
			</div>
		</div>
	</LectioThemeSurface>
{:else}
	<p class="unknown-template">Unknown Lectio template: {document.template_id}</p>
{/if}

<style>
	.unknown-template {
		padding: 1rem;
		font-size: 0.875rem;
		color: #b91c1c;
	}

	.section-stack {
		display: grid;
		gap: var(--rh-gap-section, 1.25rem);
	}
</style>
