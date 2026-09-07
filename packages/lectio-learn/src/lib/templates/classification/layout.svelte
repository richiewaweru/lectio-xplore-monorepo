<script lang="ts">
	import {
		CalloutBlock,
		ComparisonGrid,
		DefinitionFamily,
		ExplanationBlock,
		FillInTheBlank,
		HookHero,
		InsightStrip,
		PitfallAlert,
		PracticeStack,
		SectionDivider,
		ShortAnswerQuestion,
		StudentTextbox,
		SummaryBlock,
		WhatNextBridge
	} from '$lib/components/lectio';
	import type { SectionContent } from '$lib/schema/types';

	import TemplateShell from '$lib/templates/TemplateShell.svelte';

	let { section }: { section: SectionContent } = $props();
</script>

<!--
  classification — comparison grid is the spine; everything else frames it.
  Pedagogical arc: hook → callout → explanation → definition family →
                   comparison grid → insight strip → pitfall → practice → close.
-->
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

	{#if section.explanation}
		<ExplanationBlock content={section.explanation} />
	{/if}

	{#if section.definition_family}
		<DefinitionFamily content={section.definition_family} />
	{/if}

	<!-- Grid is the centrepiece -->
	{#if section.comparison_grid}
		<ComparisonGrid content={section.comparison_grid} />
	{/if}

	{#if section.insight_strip}
		<InsightStrip content={section.insight_strip} />
	{/if}

	{#if section.pitfall}
		<PitfallAlert content={section.pitfall} />
	{/if}

	{#if section.practice}
		<PracticeStack content={section.practice} mode="flat-list" />
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

	{#if section.summary}
		<SummaryBlock content={section.summary} />
	{/if}

	{#if section.what_next}
		<WhatNextBridge content={section.what_next} />
	{/if}
</TemplateShell>
