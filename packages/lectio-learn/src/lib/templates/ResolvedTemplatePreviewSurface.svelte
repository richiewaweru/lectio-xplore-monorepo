<script lang="ts">
	import { Badge } from '$lib/components/ui/badge';
	import type { TemplateDefinition, TemplatePresetDefinition } from '$lib/templates/types';

	import LectioThemeSurface from './LectioThemeSurface.svelte';

	let {
		definition,
		preset = null,
		showMetadata = true
	}: {
		definition: TemplateDefinition;
		preset?: TemplatePresetDefinition | null;
		showMetadata?: boolean;
	} = $props();

	const PreviewComponent = $derived(definition.render);
	const learnerFit = $derived(definition.contract.learnerFit.join(', ').replace(/-/g, ' '));
	const subjects = $derived(definition.contract.subjects.join(', '));
	const presetSummary = $derived(
		preset ? `${preset.name} - ${preset.palette} - ${preset.description}` : 'Default Lectio theme'
	);
</script>

<LectioThemeSurface {preset}>
	<div class="page-frame rh-gap-section">
		{#if showMetadata}
			<header class="lesson-shell rh-pad-shell">
				<div class="relative z-10 space-y-5">
					<div class="flex flex-wrap items-center gap-2">
						<Badge class="bg-primary/10 text-primary hover:bg-primary/10">
							{definition.contract.family}
						</Badge>
						<Badge variant="outline">{definition.contract.interactionLevel}</Badge>
						<Badge variant="outline">{definition.contract.intent}</Badge>
					</div>

					<div class="rh-gap-component-tight">
						<p class="eyebrow">Template preview</p>
						<h2 class="text-3xl font-serif text-primary sm:text-4xl">
							{definition.contract.name}
						</h2>
						<p class="max-w-3xl text-base leading-7 text-muted-foreground sm:text-lg sm:leading-8">
							{definition.contract.tagline}
						</p>
					</div>

					<div class="grid rh-gap-cluster md:grid-cols-2 xl:grid-cols-3">
						<div class="rh-radius-card border border-border/70 bg-white/80 p-4">
							<p class="eyebrow">Learner fit</p>
							<p class="mt-2 text-sm leading-6 text-foreground/82">{learnerFit}</p>
						</div>
						<div class="rh-radius-card border border-border/70 bg-white/80 p-4">
							<p class="eyebrow">Subjects</p>
							<p class="mt-2 text-sm leading-6 text-foreground/82">{subjects}</p>
						</div>
						<div class="rh-radius-card border border-border/70 bg-white/80 p-4 md:col-span-2 xl:col-span-1">
							<p class="eyebrow">Preset</p>
							<p class="mt-2 text-sm leading-6 text-foreground/82">{presetSummary}</p>
						</div>
					</div>
				</div>
			</header>
		{/if}

		<section class="rh-gap-component">
			<div class="space-y-2">
				<p class="eyebrow">Seeded preview</p>
				<p class="max-w-3xl text-sm leading-6 text-muted-foreground sm:text-base sm:leading-7">
					{definition.preview.summary}
				</p>
			</div>

			<PreviewComponent section={definition.preview.section} />
		</section>
	</div>
</LectioThemeSurface>
