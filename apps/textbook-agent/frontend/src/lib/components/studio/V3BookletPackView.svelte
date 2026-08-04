<script lang="ts">
	import { LectioThemeSurface, basePresetMap, templateRegistryMap } from 'lectio';
	import type { SectionContent } from 'lectio';
	import type { BookletStatus, V3DraftPack } from '$lib/types/v3';
	import V3BookletIssuesPanel from '$lib/components/studio/V3BookletIssuesPanel.svelte';
	import {
		getBookletPrintReadiness,
		getBookletStatusSummary
	} from '$lib/studio/v3-booklet';

	interface Props {
		pack: V3DraftPack;
		status: BookletStatus;
		issues?: Array<Record<string, unknown>>;
		showIssues?: boolean;
	}

	let { pack, status, issues = [], showIssues = true }: Props = $props();

	const template = $derived(templateRegistryMap[pack.template_id]);
	const preset = $derived(basePresetMap['blue-classroom'] ?? Object.values(basePresetMap)[0]);
	const printReadiness = $derived(getBookletPrintReadiness(status, pack));
	const statusSummary = $derived(getBookletStatusSummary(status));
</script>

<section class="mx-auto max-w-4xl space-y-4 px-4 py-4">
	<div class="rounded-lg border border-border/60 bg-muted/30 px-4 py-3">
		<p class="text-sm font-medium">{printReadiness.label}</p>
		<p class="mt-1 text-sm text-muted-foreground">{printReadiness.detail}</p>
		<p class="mt-2 text-xs uppercase tracking-wide text-muted-foreground">{statusSummary}</p>
	</div>

	{#if pack.warnings.length}
		<div class="rounded-lg border border-amber-300/60 bg-amber-50/60 px-4 py-3 text-sm">
			<p class="font-semibold">Warnings</p>
			<ul class="ml-5 list-disc">
				{#each pack.warnings as warning}
					<li>{warning}</li>
				{/each}
			</ul>
		</div>
	{/if}

	{#if showIssues}
		<V3BookletIssuesPanel {issues} />
	{/if}

	{#if template && preset}
		<LectioThemeSurface {preset}>
			<div class="space-y-6">
				{#each pack.sections as section, idx (String(section.section_id ?? idx))}
					{@const TemplateRender = template.render}
					<article class="rounded-xl border border-border/50 bg-card p-4 shadow-sm">
						<TemplateRender section={section as unknown as SectionContent} />
					</article>
				{/each}
			</div>
		</LectioThemeSurface>
	{:else}
		<p class="text-sm text-muted-foreground">
			Template unavailable for <code>{pack.template_id}</code>.
		</p>
	{/if}
</section>
