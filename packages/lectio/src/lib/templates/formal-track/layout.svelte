<script lang="ts">
	import {
		CalloutBlock,
		DefinitionCard,
		ExplanationBlock,
		FillInTheBlank,
		HookHero,
		KeyFact,
		PitfallAlert,
		PracticeStack,
		SectionDivider,
		ShortAnswerQuestion,
		WhatNextBridge,
		WorkedExampleCard
	} from '$lib/components/lectio';
	import type { SectionContent } from '$lib/schema/types';

	import TemplateShell from '$lib/templates/TemplateShell.svelte';

	let { section }: { section: SectionContent } = $props();
</script>

<!--
  formal-track — print-first, no sidebar, no visual ornament.
  Pedagogical arc: hook (optional) → definition → explanation → key fact →
                   worked example → pitfall → practice → close.
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

	{#if section.definition}
		<DefinitionCard content={section.definition} />
	{/if}

	{#if section.key_fact}
		<KeyFact content={section.key_fact} />
	{/if}

	{#if section.explanation}
		<ExplanationBlock content={section.explanation} />
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

	{#if section.fill_in_blank}
		<FillInTheBlank content={section.fill_in_blank} />
	{/if}

	{#if section.what_next}
		<WhatNextBridge content={section.what_next} />
	{/if}
</TemplateShell>
