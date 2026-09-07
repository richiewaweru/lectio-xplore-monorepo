<script lang="ts">
	import {
		CalloutBlock,
		DefinitionCard,
		DiagramBlock,
		ExplanationBlock,
		GlossaryRail,
		HookHero,
		PitfallAlert,
		PracticeStack,
		ReflectionPrompt,
		SectionDivider,
		ShortAnswerQuestion,
		SimulationBlock,
		StudentTextbox,
		SummaryBlock,
		WhatNextBridge,
		WorkedExampleCard
	} from '$lib/components/lectio';
	import type { SectionContent } from '$lib/schema/types';

	import TemplateShell from '$lib/templates/TemplateShell.svelte';

	let { section }: { section: SectionContent } = $props();
</script>

<!--
  guided-discovery — read first, then discover via simulation; glossary rail on desktop.
  Pedagogical arc: hook → callout → explanation → definition →
                   diagram → simulation → worked example → pitfall →
                   practice → reflection → close.
-->
<TemplateShell {section}>
	{#if section.hook}
		<HookHero content={section.hook} />
	{/if}

	{#if section.divider}
		<SectionDivider content={section.divider} />
	{/if}

	{#if section.callout}
		<CalloutBlock content={section.callout} />
	{/if}

	<!-- Main column + optional sticky glossary sidebar -->
	<div class={`grid gap-6 ${section.glossary ? 'lg:grid-cols-[1fr_280px]' : ''}`}>
		<div class="flex flex-col gap-6">
			{#if section.explanation}
				<ExplanationBlock content={section.explanation} />
			{/if}

			{#if section.definition}
				<DefinitionCard content={section.definition} />
			{/if}

			{#if section.diagram}
				<DiagramBlock content={section.diagram} />
			{/if}

			<!-- Simulation comes after explanation — learners verify what they read -->
			{#if section.simulation}
				<SimulationBlock content={section.simulation} />
			{/if}

			{#if section.worked_example}
				<WorkedExampleCard content={section.worked_example} mode="step-reveal" />
			{/if}

			{#if section.pitfall}
				<PitfallAlert content={section.pitfall} />
			{/if}

			{#if section.practice}
				<PracticeStack content={section.practice} mode="accordion" />
			{/if}

			{#if section.short_answer}
				<ShortAnswerQuestion content={section.short_answer} />
			{/if}

			{#if section.student_textbox}
				<StudentTextbox content={section.student_textbox} />
			{/if}

			{#if section.reflection}
				<ReflectionPrompt content={section.reflection} />
			{/if}
		</div>

		{#if section.glossary}
			<aside class="hidden lg:block">
				<GlossaryRail content={section.glossary} mode="sticky" />
			</aside>
		{/if}
	</div>

	<!-- Glossary collapses to inline on mobile -->
	{#if section.glossary}
		<div class="lg:hidden">
			<GlossaryRail content={section.glossary} mode="inline-strip" />
		</div>
	{/if}

	{#if section.summary}
		<SummaryBlock content={section.summary} />
	{/if}

	{#if section.what_next}
		<WhatNextBridge content={section.what_next} />
	{/if}
</TemplateShell>
