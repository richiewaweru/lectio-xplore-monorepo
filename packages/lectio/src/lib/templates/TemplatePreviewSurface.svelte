<script lang="ts">
	import { Card } from '$lib/components/ui/card';

	import LectioThemeSurface from './LectioThemeSurface.svelte';
	import ResolvedTemplatePreviewSurface from './ResolvedTemplatePreviewSurface.svelte';
	import {
		DEFAULT_PRESET_ID,
		resolveTemplateDefinition,
		resolveTemplatePreset
} from './resolver';

	let {
		templateId,
		presetId = DEFAULT_PRESET_ID,
		showMetadata = true
	}: {
		templateId: string;
		presetId?: string;
		showMetadata?: boolean;
	} = $props();

	const definition = $derived(resolveTemplateDefinition(templateId));
	const preset = $derived(definition ? resolveTemplatePreset(definition, presetId) : null);
</script>

{#if definition}
	<ResolvedTemplatePreviewSurface {definition} {preset} {showMetadata} />
{:else}
	<LectioThemeSurface>
		<div class="page-frame">
			<Card class="border-dashed bg-white/80 p-8 text-center text-muted-foreground">
				Unknown Lectio template: {templateId}
			</Card>
		</div>
	</LectioThemeSurface>
{/if}
