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
		onRetryIncomplete?: () => void | Promise<void>;
	}

	let { pack, status, issues = [], showIssues = true, onRetryIncomplete }: Props = $props();

	const template = $derived(templateRegistryMap[pack.template_id]);
	const preset = $derived(basePresetMap['blue-classroom'] ?? Object.values(basePresetMap)[0]);
	const printReadiness = $derived(getBookletPrintReadiness(status, pack));
	const statusSummary = $derived(getBookletStatusSummary(status));
	const incompleteDiagnostics = $derived(
		pack.section_diagnostics.filter((diagnostic) => diagnostic.status !== 'complete')
	);
	let retryingIncomplete = $state(false);

	async function retryIncomplete(): Promise<void> {
		if (!onRetryIncomplete || retryingIncomplete) return;
		retryingIncomplete = true;
		try {
			await onRetryIncomplete();
		} finally {
			retryingIncomplete = false;
		}
	}
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

	{#if incompleteDiagnostics.length}
		<section class="rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm" role="alert">
			<div class="flex flex-wrap items-start justify-between gap-3">
				<div>
					<p class="font-semibold">Some sections are incomplete</p>
					<p class="mt-1 text-muted-foreground">This booklet is not complete and must not be treated as final.</p>
				</div>
				{#if onRetryIncomplete}
					<button
						type="button"
						class="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-60"
						disabled={retryingIncomplete}
						onclick={retryIncomplete}
					>
						{retryingIncomplete ? 'Retrying failed sections…' : 'Retry failed sections'}
					</button>
				{/if}
			</div>
			<ul class="mt-3 space-y-2">
				{#each incompleteDiagnostics as diagnostic}
					<li class="rounded-md border border-destructive/20 bg-background/70 px-3 py-2">
						<p class="font-medium">{diagnostic.section_id} — {diagnostic.status}</p>
						{#if diagnostic.missing_components.length}
							<p class="mt-1 text-xs text-muted-foreground">Missing components: {diagnostic.missing_components.join(', ')}</p>
						{/if}
						{#if diagnostic.missing_visuals.length}
							<p class="mt-1 text-xs text-muted-foreground">Missing visuals: {diagnostic.missing_visuals.join(', ')}</p>
						{/if}
					</li>
				{/each}
			</ul>
		</section>
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
