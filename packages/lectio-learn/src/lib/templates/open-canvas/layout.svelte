<script lang="ts">
	import {
		SectionHeader,
		HookHero,
		ExplanationBlock,
		PrerequisiteStrip,
		InterviewAnchor,
		CalloutBlock,
		SummaryBlock,
		SectionDivider,
		DefinitionCard,
		DefinitionFamily,
		GlossaryRail,
		InsightStrip,
		KeyFact,
		ComparisonGrid,
		WorkedExampleCard,
		ProcessSteps,
		PracticeStack,
		QuizCheck,
		ReflectionPrompt,
		StudentTextbox,
		ShortAnswerQuestion,
		FillInTheBlank,
		PitfallAlert,
		DiagramBlock,
		DiagramCompare,
		DiagramSeries,
		TimelineBlock,
		SimulationBlock,
		WhatNextBridge
	} from '$lib/components/lectio';
	import type { SectionContent } from '$lib/schema/types';

	let { section }: { section: SectionContent } = $props();
</script>

<article class="mx-auto max-w-3xl rh-gap-section px-4 py-8">
	{#if section.header}
		<SectionHeader content={section.header} />
	{/if}

	{#if section.hook}
		<HookHero content={section.hook} />
	{/if}

	{#if section.prerequisites}
		<PrerequisiteStrip content={section.prerequisites} />
	{/if}

	{#if section.interview}
		<InterviewAnchor content={section.interview} />
	{/if}

	{#if section.callout}
		<CalloutBlock content={section.callout} />
	{/if}

	{#if section.divider}
		<SectionDivider content={section.divider} />
	{/if}

	{#if section.key_fact}
		<KeyFact content={section.key_fact} />
	{/if}

	{#if section.explanation}
		<ExplanationBlock content={section.explanation} />
	{/if}

	{#if section.definition}
		<DefinitionCard content={section.definition} />
	{/if}

	{#if section.definition_family}
		<DefinitionFamily content={section.definition_family} />
	{/if}

	{#if section.glossary}
		<GlossaryRail content={section.glossary} mode="drawer" />
	{/if}

	{#if section.insight_strip}
		<InsightStrip content={section.insight_strip} />
	{/if}

	{#if section.comparison_grid}
		<ComparisonGrid content={section.comparison_grid} />
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

	{#if section.simulation}
		<SimulationBlock content={section.simulation} />
	{/if}

	{#if section.worked_example}
		<WorkedExampleCard content={section.worked_example} />
	{/if}

	{#if section.process}
		<ProcessSteps content={section.process} />
	{/if}

	{#if section.practice}
		<PracticeStack content={section.practice} />
	{/if}

	{#if section.quiz}
		<QuizCheck content={section.quiz} />
	{/if}

	{#if section.reflection}
		<ReflectionPrompt content={section.reflection} />
	{/if}

	{#if section.student_textbox}
		<StudentTextbox content={section.student_textbox} />
	{/if}

	{#if section.short_answer}
		<ShortAnswerQuestion content={section.short_answer} />
	{/if}

	{#if section.fill_in_blank}
		<FillInTheBlank content={section.fill_in_blank} />
	{/if}

	{#if section.pitfall}
		<PitfallAlert content={section.pitfall} />
	{/if}

	{#if section.summary}
		<SummaryBlock content={section.summary} />
	{/if}

	{#if section.what_next}
		<WhatNextBridge content={section.what_next} />
	{/if}
</article>
