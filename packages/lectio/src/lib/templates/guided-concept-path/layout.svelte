<script lang="ts">
	import {
		CalloutBlock,
		ComparisonGrid,
		DefinitionCard,
		DefinitionFamily,
		DiagramBlock,
		DiagramCompare,
		DiagramSeries,
		ExplanationBlock,
		FillInTheBlank,
		GlossaryRail,
		HookHero,
		ImageBlock,
		InsightStrip,
		InterviewAnchor,
		KeyFact,
		PitfallAlert,
		PracticeStack,
		PrerequisiteStrip,
		ProcessSteps,
		QuizCheck,
		ReflectionPrompt,
		SectionDivider,
		ShortAnswerQuestion,
		SimulationBlock,
		StudentTextbox,
		SummaryBlock,
		TimelineBlock,
		VideoEmbed,
		WhatNextBridge,
		WorkedExampleCard
	} from '$lib/components/lectio';
	import type { SectionContent } from '$lib/schema/types';

	import TemplateShell from '$lib/templates/TemplateShell.svelte';

	let { section }: { section: SectionContent } = $props();
</script>

<!--
  guided-concept-path — main reading column + optional sticky glossary rail.
  Pedagogical arc: hook → knowledge anchors → explanation → example → practice → close.
-->
<TemplateShell {section}>
	{#if section.hook}
		<HookHero content={section.hook} />
	{/if}

	{#if section.prerequisites}
		<PrerequisiteStrip content={section.prerequisites} />
	{/if}

	{#if section.interview}
		<InterviewAnchor content={section.interview} />
	{/if}

	{#if section.divider}
		<SectionDivider content={section.divider} />
	{/if}

	{#if section.callout}
		<CalloutBlock content={section.callout} />
	{/if}

	{#if section.key_fact}
		<KeyFact content={section.key_fact} />
	{/if}

	{#if section.definition}
		<DefinitionCard content={section.definition} />
	{/if}

	{#if section.definition_family}
		<DefinitionFamily content={section.definition_family} />
	{/if}

	{#if section.diagram}
		<DiagramBlock content={section.diagram} />
	{/if}

	{#if section.diagram_compare}
		<DiagramCompare content={section.diagram_compare} />
	{/if}

	{#if section.diagram_series}
		<DiagramSeries content={section.diagram_series} />
	{/if}

	{#if section.timeline}
		<TimelineBlock content={section.timeline} />
	{/if}

	{#if section.image_block}
		<ImageBlock content={section.image_block} />
	{/if}

	{#if section.video_embed}
		<VideoEmbed content={section.video_embed} />
	{/if}

	{#if section.simulation}
		<SimulationBlock content={section.simulation} />
	{/if}

	<!-- Main column + glossary sidebar on desktop -->
	<div class={`grid gap-6 ${section.glossary ? 'lg:grid-cols-[1fr_280px]' : ''}`}>
		<div class="flex flex-col gap-6">
			{#if section.explanation}
				<ExplanationBlock content={section.explanation} />
			{/if}

			{#if section.insight_strip}
				<InsightStrip content={section.insight_strip} />
			{/if}

			{#if section.comparison_grid}
				<ComparisonGrid content={section.comparison_grid} />
			{/if}

			{#if section.worked_example}
				<WorkedExampleCard content={section.worked_example} mode="step-reveal" />
			{/if}

			{#if section.process}
				<ProcessSteps content={section.process} mode="step-reveal" />
			{/if}

			{#if section.pitfall}
				<PitfallAlert content={section.pitfall} />
			{/if}

			{#if section.practice}
				<PracticeStack content={section.practice} mode="accordion" />
			{/if}

			{#if section.quiz}
				<QuizCheck content={section.quiz} />
			{/if}

			{#if section.fill_in_blank}
				<FillInTheBlank content={section.fill_in_blank} />
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
