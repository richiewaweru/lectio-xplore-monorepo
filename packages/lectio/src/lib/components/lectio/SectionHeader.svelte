<script lang="ts">
	import type { SectionHeaderContent } from '$lib/schema/types';
	import { Badge } from '$lib/components/ui/badge';
	import { Card } from '$lib/components/ui/card';

	let { content }: { content: SectionHeaderContent } = $props();

	const pillTone: Record<string, string> = {
		all: 'border-slate-200 bg-slate-50 text-slate-700',
		warm: 'border-emerald-200 bg-emerald-50 text-emerald-700',
		medium: 'border-amber-200 bg-amber-50 text-amber-700',
		cold: 'border-sky-200 bg-sky-50 text-sky-700'
	};
</script>

<Card class="border-primary/10 bg-primary text-primary-foreground" data-lectio-block="section-header" data-print-container="atomic">
	<div class="rh-gap-component rh-pad-shell">
		<div class="flex flex-wrap items-center gap-2" data-print-role="section-header-meta">
			{#if content.section_number}
				<Badge class="bg-white/12 text-primary-foreground hover:bg-white/12">
					{content.section_number}
				</Badge>
			{/if}
			<Badge class="bg-white/12 text-primary-foreground hover:bg-white/12">
				{content.subject}
			</Badge>
			<Badge variant="outline" class="border-white/20 text-primary-foreground">
				{content.grade_band}
			</Badge>
		</div>

		<div class="space-y-2">
			<h1 class="text-4xl font-semibold text-primary-foreground font-serif sm:text-5xl">
				{content.title}
			</h1>
			{#if content.subtitle}
				<p class="max-w-3xl text-lg leading-8 text-primary-foreground/76">
					{content.subtitle}
				</p>
			{/if}
		</div>

		{#if content.objectives?.length}
			<div class="max-w-2xl space-y-1">
				<span class="text-sm font-semibold uppercase tracking-[0.18em] text-primary-foreground/65">
					Objectives
				</span>
				<ul class="list-disc list-inside space-y-0.5 text-base leading-7 text-primary-foreground/86">
					{#each content.objectives as obj}
						<li>{obj}</li>
					{/each}
				</ul>
			</div>
		{/if}

		{#if content.level_pills?.length}
			<div class="flex flex-wrap gap-2" data-print-role="section-header-level-pills">
				{#each content.level_pills as pill}
					<Badge variant="outline" class={pillTone[pill.variant] ?? pillTone.all}>
						{pill.label}
					</Badge>
				{/each}
			</div>
		{/if}
	</div>
</Card>
