<script lang="ts">
	import { Card } from '$lib/components/ui/card';
	import type { SectionContent } from '$lib/schema/types';

	import LectioThemeSurface from './LectioThemeSurface.svelte';
	import {
		DEFAULT_PRESET_ID,
		resolveTemplateDefinition,
		resolveTemplatePreset
} from './resolver';

	let {
		templateId,
		section,
		presetId = DEFAULT_PRESET_ID
	}: {
		templateId: string;
		section: SectionContent;
		presetId?: string;
	} = $props();

	const definition = $derived(resolveTemplateDefinition(templateId));
	const preset = $derived(definition ? resolveTemplatePreset(definition, presetId) : null);
	const TemplateComponent = $derived(definition?.render ?? null);
</script>

<LectioThemeSurface {preset}>
	{#if TemplateComponent}
		<TemplateComponent {section} />
	{:else}
		<div class="page-frame">
			<Card class="border-dashed bg-white/80 p-8 text-center text-muted-foreground">
				Unknown Lectio template: {templateId}
			</Card>
		</div>
	{/if}
</LectioThemeSurface>
