<script lang="ts">
	import {
		CalloutBlock,
		DefinitionCard,
		DiagramBlock,
		DiagramCompare,
		DiagramSeries,
		ExplanationBlock,
		GlossaryRail,
		HookHero,
		KeyFact,
		PitfallAlert,
		PracticeStack,
		ProcessSteps,
		SectionDivider,
		ShortAnswerQuestion,
		StudentTextbox,
		SummaryBlock,
		WhatNextBridge,
		WorkedExampleCard
	} from '$lib/components/lectio';
	import type { SectionContent } from '$lib/schema/types';

	import TemplateShell from '$lib/templates/TemplateShell.svelte';

	let { section }: { section: SectionContent } = $props();
</script>

<TemplateShell {section} singleColumn>
	{#if section.hook}
		<HookHero content={section.hook} />
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

	<!--
		Diagram slot — renders whichever visual the media subsystem produced.
		diagram_series takes priority for visual-role sections (4-frame step sequence).
		diagram (single) renders below if diagram_series is absent.
	-->
	{#if section.diagram_series}
		<DiagramSeries content={section.diagram_series} />
	{/if}

	{#if section.diagram}
		<DiagramBlock content={section.diagram} />
	{/if}

	{#if section.diagram_compare}
		<DiagramCompare content={section.diagram_compare} />
	{/if}

	<div class="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
		{#if section.explanation}
			<ExplanationBlock content={section.explanation} />
		{/if}
		{#if section.process}
			<ProcessSteps content={section.process} mode="step-reveal" />
		{/if}
	</div>

	{#if section.definition}
		<DefinitionCard content={section.definition} />
	{/if}

	{#if section.worked_example}
		<WorkedExampleCard content={section.worked_example} mode="static" />
	{/if}

	{#if section.glossary}
		<GlossaryRail content={section.glossary} mode="inline-strip" />
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

	{#if section.summary}
		<SummaryBlock content={section.summary} />
	{/if}

	{#if section.what_next}
		<WhatNextBridge content={section.what_next} />
	{/if}
</TemplateShell>
