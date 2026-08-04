<script lang="ts">
	import type { MediaReference, VideoEmbedContent } from 'lectio';
	import { Film } from 'lucide-svelte';
	import { connectivityStore } from '$lib/builder/stores/connectivity.svelte';
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
		SectionHeader,
		ShortAnswerQuestion,
		SimulationBlock,
		StudentTextbox,
		VideoEmbed,
		ImageBlock,
		SummaryBlock,
		TimelineBlock,
		WhatNextBridge,
		WorkedExampleCard
	} from 'lectio';

	let {
		componentId,
		content,
		media = {}
	}: {
		componentId: string;
		content: Record<string, unknown>;
		media?: Record<string, MediaReference>;
	} = $props();

	const componentMap: Record<string, unknown> = {
		'section-header': SectionHeader,
		'hook-hero': HookHero,
		'explanation-block': ExplanationBlock,
		'prerequisite-strip': PrerequisiteStrip,
		'what-next-bridge': WhatNextBridge,
		'interview-anchor': InterviewAnchor,
		'callout-block': CalloutBlock,
		'summary-block': SummaryBlock,
		'section-divider': SectionDivider,
		'definition-card': DefinitionCard,
		'definition-family': DefinitionFamily,
		'glossary-rail': GlossaryRail,
		'insight-strip': InsightStrip,
		'key-fact': KeyFact,
		'comparison-grid': ComparisonGrid,
		'worked-example-card': WorkedExampleCard,
		'process-steps': ProcessSteps,
		'practice-stack': PracticeStack,
		'quiz-check': QuizCheck,
		'reflection-prompt': ReflectionPrompt,
		'student-textbox': StudentTextbox,
		'short-answer': ShortAnswerQuestion,
		'fill-in-blank': FillInTheBlank,
		'pitfall-alert': PitfallAlert,
		'diagram-block': DiagramBlock,
		'diagram-compare': DiagramCompare,
		'diagram-series': DiagramSeries,
		'timeline-block': TimelineBlock,
		'simulation-block': SimulationBlock
	};

	const Component = $derived(componentMap[componentId] as typeof SectionHeader | undefined);

	const videoContent = $derived(content as unknown as VideoEmbedContent);
	const videoRef = $derived(videoContent.media_id ? media[videoContent.media_id] : undefined);
	const videoUrl = $derived(videoRef?.type === 'video' ? videoRef.url : undefined);
</script>

{#if componentId === 'video-embed'}
	{#if connectivityStore.online}
		<VideoEmbed content={content as never} {media} />
	{:else}
		<div
			class="video-offline-placeholder rounded-lg border border-slate-200 bg-slate-50 p-6 text-center text-slate-700"
		>
			<div class="mb-2 flex justify-center text-slate-500">
				<Film size={32} aria-hidden="true" />
			</div>
			<p class="text-sm font-medium">Video available when online</p>
			{#if videoUrl}
				<p class="mt-1 break-all text-xs text-slate-500">{videoUrl}</p>
			{/if}
			{#if videoContent.caption}
				<p class="mt-2 text-xs text-slate-600">{videoContent.caption}</p>
			{/if}
		</div>
	{/if}
{:else if componentId === 'image-block'}
	<ImageBlock content={content as never} {media} />
{:else if componentId === 'diagram-block'}
	<DiagramBlock content={content as never} {media} />
{:else if componentId === 'diagram-compare'}
	<DiagramCompare content={content as never} {media} />
{:else if componentId === 'diagram-series'}
	<DiagramSeries content={content as never} {media} />
{:else if Component}
	<Component content={content as never} />
{:else}
	<div class="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
		Unknown component: {componentId}
	</div>
{/if}
