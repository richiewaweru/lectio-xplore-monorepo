<script lang="ts">
	import {
		CalloutBlock,
		DefinitionCard,
		ExplanationBlock,
		HookHero,
		PitfallAlert,
		PracticeStack,
		ReflectionPrompt,
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

<!--
  low-load — single column, short chunks, no sidebar.
  Pedagogical arc: hook → callout → explanation → definition → worked example →
                   pitfall → practice → reflection → close.
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

	{#if section.definition}
		<DefinitionCard content={section.definition} />
	{/if}

	{#if section.worked_example}
		<WorkedExampleCard content={section.worked_example} mode="static" />
	{/if}

	{#if section.pitfall}
		<PitfallAlert content={section.pitfall} />
	{/if}

	{#if section.practice}
		<PracticeStack content={section.practice} mode="flat-list" />
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

	{#if section.summary}
		<SummaryBlock content={section.summary} />
	{/if}

	{#if section.what_next}
		<WhatNextBridge content={section.what_next} />
	{/if}
</TemplateShell>
