<script lang="ts">
	import type { V3StructuralPlan } from '$lib/types/v3';

	interface Props {
		plan: V3StructuralPlan;
	}

	let { plan }: Props = $props();
</script>

<div class="mx-auto max-w-3xl space-y-6 px-4 py-8">
	<header class="rounded-xl border border-border/60 bg-card p-5">
		<p class="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Structural plan</p>
		<h2 class="mt-2 text-xl font-semibold">{plan.lesson_intent.goal}</h2>
		<p class="mt-2 text-sm text-muted-foreground">{plan.lesson_intent.structure_rationale}</p>
		<p class="mt-3 text-sm">
			<span class="font-medium">Anchor:</span> {plan.anchor.example}
		</p>
		<p class="text-xs text-muted-foreground">Reuse: {plan.anchor.reuse_scope}</p>
	</header>

	<section class="space-y-3">
		<h3 class="text-base font-semibold">Section sequence</h3>
		<ol class="space-y-3">
			{#each plan.sections as section, index}
				<li class="rounded-xl border border-border/60 bg-card p-4">
					<div class="flex items-center justify-between gap-2">
						<p class="font-semibold">{index + 1}. {section.title}</p>
						<span class="rounded-full bg-muted px-2 py-0.5 text-xs uppercase">{section.role}</span>
					</div>
					<p class="mt-1 text-xs text-muted-foreground">
						{section.visual_required ? 'Visual required' : 'No visual required'}
					</p>
					{#if section.transition_note}
						<p class="mt-2 text-xs text-muted-foreground">{section.transition_note}</p>
					{/if}
					<ul class="mt-2 list-inside list-disc text-sm">
						{#each section.components as component}
							<li><span class="font-medium">{component.slug}</span> — {component.purpose}</li>
						{/each}
					</ul>
				</li>
			{/each}
		</ol>
	</section>

	{#if plan.question_plan.length}
		<section class="rounded-xl border border-border/60 bg-card p-4">
			<h3 class="text-base font-semibold">Question arc</h3>
			<ul class="mt-2 list-inside list-disc text-sm">
				{#each plan.question_plan as q}
					<li>
						{q.question_id} → {q.section_id} ({q.temperature}{q.diagram_required ? ', diagram' : ''})
					</li>
				{/each}
			</ul>
		</section>
	{/if}
</div>
