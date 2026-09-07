<script lang="ts">
	import {
		CalloutBlock,
		DefinitionCard,
		DiagramBlock,
		DiagramCompare,
		DiagramSeries,
		ExplanationBlock,
		HookHero,
		KeyFact,
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
  visual-led — the figure leads, prose follows.
  Pedagogical arc: hook → visual anchor → explanation → support → practice → close.
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

	{#if section.key_fact}
		<KeyFact content={section.key_fact} />
	{/if}

	<!-- Diagram family — visual anchor above the prose -->
	{#if section.diagram_series}
		<DiagramSeries content={section.diagram_series} />
	{/if}

	{#if section.diagram}
		<DiagramBlock content={section.diagram} />
	{/if}

	{#if section.diagram_compare}
		<DiagramCompare content={section.diagram_compare} />
	{/if}

	{#if section.explanation}
		<ExplanationBlock content={section.explanation} />
	{/if}

	{#if section.definition}
		<DefinitionCard content={section.definition} />
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
