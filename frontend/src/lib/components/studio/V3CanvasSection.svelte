<script lang="ts">
	import type { CanvasSection } from '$lib/types/v3';
	import V3CanvasComponent from '$lib/components/studio/V3CanvasComponent.svelte';
	import V3CanvasVisual from '$lib/components/studio/V3CanvasVisual.svelte';
	import V3LectioSectionEmbed from '$lib/components/studio/V3LectioSectionEmbed.svelte';

	interface Props {
		section: CanvasSection;
		templateId: string;
		onRetrySection?: (sectionId: string) => void;
		debugInspect?: boolean;
	}

	let { section, templateId, onRetrySection, debugInspect = import.meta.env.DEV }: Props = $props();

	const orderedFields = $derived.by(() => {
		const raw = section.mergedFields?._component_order;
		if (Array.isArray(raw)) {
			return raw.filter(
				(field): field is string =>
					typeof field === 'string' && field in section.mergedFields && !field.startsWith('_')
			);
		}
		return section.components.map((component) => component.id);
	});
</script>

<div
	class="v3-canvas-section space-y-4 rounded-xl border border-border/60 bg-muted/20 p-4"
	class:border-primary={section.sectionStatus === 'running'}
	id="section-{section.id}"
>
	<div class="flex flex-col gap-1 border-b border-border/40 pb-3">
		<h3 class="text-lg font-semibold tracking-tight">{section.title}</h3>
		<p class="text-xs text-muted-foreground">{section.teacher_labels}</p>
		{#if section.sectionStatus === 'running'}
			<p class="text-xs font-medium text-primary">Planning…</p>
		{/if}
	</div>

	{#if section.sectionStatus === 'failed'}
		<div class="rounded-lg border border-destructive/30 bg-destructive/5 p-4">
			<p class="text-sm font-semibold text-destructive">Section failed</p>
			<p class="mt-1 text-sm text-muted-foreground">
				{section.diagnosticWarnings[0] ?? 'This section could not be rendered yet.'}
			</p>
			{#if section.missingComponents.length || section.missingVisuals.length}
				<p class="mt-2 text-xs text-muted-foreground">
					Missing: {[...section.missingComponents, ...section.missingVisuals].join(', ')}
				</p>
			{/if}
			{#if onRetrySection}
				<button
					type="button"
					class="mt-3 rounded-md border border-input px-3 py-1.5 text-xs font-semibold"
					onclick={() => onRetrySection(section.id)}
				>
					Retry section
				</button>
			{/if}
		</div>
	{:else}
		{#if section.sectionStatus === 'incomplete'}
			<div class="rounded-lg border border-amber-300/60 bg-amber-50 p-3 text-sm text-amber-950">
				<p class="font-semibold">Section partially rendered</p>
				<p class="mt-1 text-xs text-amber-900/80">
					{section.diagnosticWarnings[0] ?? 'Some planned content is still missing.'}
				</p>
			</div>
		{/if}

		{#if section.visual}
			<V3CanvasVisual visual={section.visual} />
		{/if}

		{#if section.stage2Preview && section.components.every((component) => component.status === 'pending')}
			<div class="stage2-preview space-y-2 rounded-md border border-border/30 bg-muted/10 p-3">
				{#each section.stage2Preview.componentIntents as item (item.componentId)}
					<p class="text-xs text-muted-foreground">
						<span class="font-medium">{item.componentId}:</span> {item.intent}
					</p>
				{/each}
				{#each section.stage2Preview.questionPrompts as prompt, i}
					<p class="text-xs italic text-muted-foreground">Q{i + 1}: {prompt}</p>
				{/each}
				{#if section.stage2Preview.visualSubject}
					<p class="text-xs text-muted-foreground">
						Diagram: {section.stage2Preview.visualSubject}
					</p>
				{/if}
			</div>
		{/if}

		<div class="space-y-2">
			{#each section.components as component (component.id)}
				<V3CanvasComponent {component} />
			{/each}
		</div>

		{#if Array.isArray(section.mergedFields?._component_order) && orderedFields.length}
			<div class="space-y-2 rounded-md border border-border/40 bg-background/60 p-3">
				<h4 class="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Blueprint Order</h4>
				{#each orderedFields as fieldKey (fieldKey)}
					{#if section.mergedFields[fieldKey]}
						<div class="rounded border border-border/30 px-2 py-1 text-xs">
							<span class="font-medium">{fieldKey}</span>
						</div>
					{/if}
				{/each}
			</div>
		{/if}

		{#if section.questions.length}
			<div class="space-y-2">
				<h4 class="text-sm font-semibold">Practice</h4>
				{#each section.questions as q (q.id)}
					<div class="rounded-md border border-border/40 p-2 text-sm">
						<span class="mr-2 rounded bg-muted px-2 py-0.5 text-xs uppercase">{q.difficulty}</span>
						{#if q.status === 'pending'}
							<span class="text-muted-foreground">Waiting...</span>
						{:else}
							<span class="text-muted-foreground">Ready</span>
						{/if}
					</div>
				{/each}
			</div>
		{/if}

		<V3LectioSectionEmbed {templateId} sectionId={section.id} title={section.title} mergedFields={section.mergedFields} />

		{#if debugInspect}
			<details class="rounded border border-border/40 bg-background/60 p-2">
				<summary class="cursor-pointer text-xs font-medium text-muted-foreground">Inspect section</summary>
				<pre class="mt-2 overflow-auto whitespace-pre-wrap text-[11px]">{JSON.stringify(section.mergedFields, null, 2)}</pre>
			</details>
		{/if}
	{/if}
</div>
