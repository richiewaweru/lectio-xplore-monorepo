<script lang="ts">
	import { Badge } from '$lib/components/ui/badge';
	import { Card } from '$lib/components/ui/card';
	import { getTemplateById } from '$lib/templates/registry';
	import TemplateContractPanel from '$lib/templates/TemplateContractPanel.svelte';
	import TemplateContractDrawer from '$lib/templates/TemplateContractDrawer.svelte';
	import TemplatePreviewSurface from '$lib/templates/TemplatePreviewSurface.svelte';
	import { cn } from '$lib/utils';

	let { templateId }: { templateId: string } = $props();
	let desktopContractOpen = $state(false);
	let isDesktopContractLayout = $state(false);

	const definition = $derived(getTemplateById(templateId));
</script>

{#if definition}
	<div class="page-frame space-y-8">
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
					<p class="eyebrow">Template detail</p>
					<h1 class="text-4xl text-primary font-serif sm:text-5xl">
						{definition.contract.name}
					</h1>
					<p class="max-w-3xl text-lg leading-8 text-muted-foreground">
						{definition.contract.tagline}
					</p>
				</div>
				<div class="flex flex-wrap rh-gap-cluster">
					<a
						href="/templates"
						class="inline-flex items-center rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
					>
						Back to gallery
					</a>
					<TemplateContractDrawer
						contract={definition.contract}
						presets={definition.presets}
						bind:desktopOpen={desktopContractOpen}
						bind:isDesktop={isDesktopContractLayout}
					/>
					<a
						href="/components"
						class="inline-flex items-center rounded-xl border border-input bg-background px-4 py-2.5 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
					>
						View components
					</a>
				</div>
			</div>
		</header>

		<div
			class={cn(
				'rh-gap-section',
				isDesktopContractLayout &&
					desktopContractOpen &&
					'md:grid md:grid-cols-[22rem_minmax(0,1fr)] md:items-start md:gap-6 md:space-y-0 lg:grid-cols-[24rem_minmax(0,1fr)]'
			)}
		>
			{#if isDesktopContractLayout && desktopContractOpen}
				<aside
					id="template-contract-panel"
					aria-label="Template contract"
					class="md:sticky md:top-6 md:max-h-[calc(100vh-1.5rem)] md:overflow-y-auto"
				>
					<div class="rh-radius-outer border border-white/60 bg-white/82 rh-pad-card shadow-[0_12px_36px_rgba(15,23,42,0.08)]">
						<TemplateContractPanel
							contract={definition.contract}
							presets={definition.presets}
						/>
					</div>
				</aside>
			{/if}

			<section class="rh-gap-component md:min-w-0">
				<TemplatePreviewSurface
					templateId={templateId}
					presetId={definition.presets[0]?.id}
					showMetadata={false}
				/>
			</section>
		</div>
	</div>
{:else}
	<div class="page-frame">
		<Card class="border-dashed bg-white/80 p-8 text-center text-muted-foreground">
			Template not found.
		</Card>
	</div>
{/if}
