// Capacity warnings — not hard errors, just console warnings
// Prevents content from quietly overflowing components

import type {
	ComparisonGridContent,
	DiagramCompareContent,
	DiagramContent,
	DiagramSeriesContent,
	ImageBlockContent,
	SectionContent,
	SimulationContent,
	TimelineContent,
	VideoEmbedContent
} from './types';

function words(text: string): number {
	return text.trim().split(/\s+/).filter(Boolean).length;
}

function comparisonValueText(value: string | { text: string }): string {
	return typeof value === 'string' ? value : value.text;
}

function warn(location: string, message: string): string {
	return `[Lectio/${location}] ${message}`;
}

function validateComparisonGrid(content: ComparisonGridContent, warnings: string[]) {
	if (words(content.title) > 10) warnings.push(warn('ComparisonGrid', 'title exceeds 10 words'));
	if (content.intro && words(content.intro) > 60)
		warnings.push(warn('ComparisonGrid', 'intro exceeds 60 words'));
	if (content.columns.length < 2 || content.columns.length > 4)
		warnings.push(
			warn('ComparisonGrid', `has ${content.columns.length} columns; expected between 2 and 4`)
		);

	content.columns.forEach((column, index) => {
		if (words(column.title) > 6)
			warnings.push(warn('ComparisonGrid', `column ${index + 1} title exceeds 6 words`));
		if (words(column.summary) > 24)
			warnings.push(warn('ComparisonGrid', `column ${index + 1} summary exceeds 24 words`));
		if (column.detail && words(column.detail) > 50)
			warnings.push(warn('ComparisonGrid', `column ${index + 1} detail exceeds 50 words`));
	});

	if (content.rows.length > 6)
		warnings.push(warn('ComparisonGrid', `has ${content.rows.length} rows; max is 6`));

	content.rows.forEach((row, index) => {
		if (words(row.criterion) > 8)
			warnings.push(warn('ComparisonGrid', `row ${index + 1} criterion exceeds 8 words`));
		if (row.values.length !== content.columns.length)
			warnings.push(
				warn(
					'ComparisonGrid',
					`row ${index + 1} has ${row.values.length} values; expected ${content.columns.length}`
				)
			);
		row.values.forEach((value, valueIndex) => {
			if (words(comparisonValueText(value)) > 20)
				warnings.push(
					warn('ComparisonGrid', `row ${index + 1} value ${valueIndex + 1} exceeds 20 words`)
				);
		});
		if (row.takeaway && words(row.takeaway) > 24)
			warnings.push(warn('ComparisonGrid', `row ${index + 1} takeaway exceeds 24 words`));
	});
}

function validateTimeline(content: TimelineContent, warnings: string[]) {
	if (words(content.title) > 10) warnings.push(warn('TimelineBlock', 'title exceeds 10 words'));
	if (content.intro && words(content.intro) > 60)
		warnings.push(warn('TimelineBlock', 'intro exceeds 60 words'));
	if (content.events.length < 3) warnings.push(warn('TimelineBlock', 'requires at least 3 events'));
	if (content.events.length > 8)
		warnings.push(warn('TimelineBlock', `has ${content.events.length} events; max is 8`));

	content.events.forEach((event, index) => {
		if (words(event.title) > 8)
			warnings.push(warn('TimelineBlock', `event ${index + 1} title exceeds 8 words`));
		if (words(event.summary) > 50)
			warnings.push(warn('TimelineBlock', `event ${index + 1} summary exceeds 50 words`));
		if (event.impact && words(event.impact) > 24)
			warnings.push(warn('TimelineBlock', `event ${index + 1} impact exceeds 24 words`));
		if (event.tags && event.tags.length > 3)
			warnings.push(
				warn('TimelineBlock', `event ${index + 1} has ${event.tags.length} tags; max is 3`)
			);
	});

	if (content.closing_takeaway && words(content.closing_takeaway) > 40)
		warnings.push(warn('TimelineBlock', 'closing_takeaway exceeds 40 words'));
}

function validateDiagram(content: DiagramContent, location: string, warnings: string[]) {
	const hasSvg = Boolean(content.svg_content?.trim());
	const hasImage = Boolean(content.media_id?.trim()) || Boolean(content.image_url?.trim());
	if (!hasSvg && !hasImage) warnings.push(warn(location, 'requires media_id, svg_content, or image_url'));
	if (words(content.caption) > 60) warnings.push(warn(location, 'caption exceeds 60 words'));
	if (words(content.alt_text) > 80) warnings.push(warn(location, 'alt_text exceeds 80 words'));
	if (content.callouts && content.callouts.length > 6)
		warnings.push(warn(location, 'callouts max 6'));
	if (content.callouts?.length && !hasSvg)
		warnings.push(warn(location, 'callouts require svg_content'));
}

function validateDiagramCompare(content: DiagramCompareContent, warnings: string[]) {
	const hasSvgPair = Boolean(content.before_svg?.trim()) && Boolean(content.after_svg?.trim());
	const hasImagePair =
		(Boolean(content.before_media_id?.trim()) || Boolean(content.before_image_url?.trim())) &&
		(Boolean(content.after_media_id?.trim()) || Boolean(content.after_image_url?.trim()));
	if (!hasSvgPair && !hasImagePair)
		warnings.push(
			warn(
				'DiagramCompare',
				'requires a full before/after svg pair or a full before/after image pair'
			)
		);
	if (words(content.before_label) > 6)
		warnings.push(warn('DiagramCompare', 'before_label exceeds 6 words'));
	if (words(content.after_label) > 6)
		warnings.push(warn('DiagramCompare', 'after_label exceeds 6 words'));
	if (words(content.caption) > 60) warnings.push(warn('DiagramCompare', 'caption exceeds 60 words'));
}

function validateDiagramSeries(content: DiagramSeriesContent, warnings: string[]) {
	if (words(content.title) > 10) warnings.push(warn('DiagramSeries', 'title exceeds 10 words'));
	if (content.diagrams.length > 4) warnings.push(warn('DiagramSeries', 'diagrams max 4'));

	content.diagrams.forEach((diagram, index) => {
		const hasSvg = Boolean(diagram.svg_content?.trim());
		const hasImage = Boolean(diagram.media_id?.trim()) || Boolean(diagram.image_url?.trim());
		if (!hasSvg && !hasImage)
			warnings.push(
				warn('DiagramSeries', `diagram ${index + 1} requires media_id, svg_content, or image_url`)
			);
		if (words(diagram.step_label) > 8)
			warnings.push(warn('DiagramSeries', `diagram ${index + 1} step_label exceeds 8 words`));
		if (words(diagram.caption) > 40)
			warnings.push(warn('DiagramSeries', `diagram ${index + 1} caption exceeds 40 words`));
	});
}

function validateVideoEmbed(content: VideoEmbedContent, warnings: string[]) {
	if (!content.media_id?.trim()) warnings.push(warn('VideoEmbed', 'media_id is empty'));
	if (content.caption && words(content.caption) > 40)
		warnings.push(warn('VideoEmbed', 'caption exceeds 40 words'));
}

function validateImageBlock(content: ImageBlockContent, warnings: string[]) {
	if (!content.media_id?.trim()) warnings.push(warn('ImageBlock', 'media_id is empty'));
	if (!content.alt_text?.trim()) warnings.push(warn('ImageBlock', 'alt_text is empty (add for accessibility)'));
	if (words(content.alt_text) > 80) warnings.push(warn('ImageBlock', 'alt_text exceeds 80 words'));
	if (content.caption && words(content.caption) > 40)
		warnings.push(warn('ImageBlock', 'caption exceeds 40 words'));
}

function validateSimulation(content: SimulationContent, warnings: string[]) {
	if (words(content.spec.goal) > 40) warnings.push(warn('SimulationBlock', 'goal exceeds 40 words'));
	if (content.explanation && words(content.explanation) > 60)
		warnings.push(warn('SimulationBlock', 'explanation exceeds 60 words'));
	if (content.spec.dimensions.height <= 0)
		warnings.push(warn('SimulationBlock', 'dimensions.height must be positive'));
	if (content.fallback_diagram)
		validateDiagram(content.fallback_diagram, 'SimulationBlock/FallbackDiagram', warnings);
}

export function validateSection(section: SectionContent): string[] {
	const w: string[] = [];

	// Header
	if (section.header) {
		if (words(section.header.title) > 12)
			w.push(warn('SectionHeader', 'title exceeds 12 words'));
		if (section.header.objectives) {
			for (const obj of section.header.objectives) {
				if (words(obj) > 30) {
					w.push(warn('SectionHeader', 'an objective exceeds 30 words'));
					break;
				}
			}
		}
	}

	// Hook
	if (section.hook) {
		if (words(section.hook.headline) > 12)
			w.push(warn('HookHero', 'headline exceeds 12 words'));
		if (words(section.hook.body) > 80)
			w.push(warn('HookHero', 'body exceeds 80 words'));
		if (section.hook.question_options && section.hook.question_options.length > 3)
			w.push(warn('HookHero', 'question_options max 3'));
	}

	// Explanation
	if (section.explanation) {
		if (words(section.explanation.body) > 350)
			w.push(warn('ExplanationBlock', 'body exceeds 350 words'));
		if (section.explanation.emphasis.length > 3)
			w.push(warn('ExplanationBlock', 'emphasis max 3 items'));
		if (section.explanation.callouts) {
			if (section.explanation.callouts.length > 3)
				w.push(warn('ExplanationBlock', 'callouts max 3'));
			section.explanation.callouts.forEach((c, i) => {
				if (words(c.text) > 60)
					w.push(warn(`ExplanationBlock callout ${i + 1}`, 'text exceeds 60 words'));
			});
		}
	}

	// Prerequisites
	if (section.prerequisites && section.prerequisites.items.length > 4)
		w.push(warn('PrerequisiteStrip', 'items max 4'));

	// Definition
	if (section.definition) {
		if (words(section.definition.formal) > 80)
			w.push(warn('DefinitionCard', 'formal exceeds 80 words'));
		if (words(section.definition.plain) > 60)
			w.push(warn('DefinitionCard', 'plain exceeds 60 words'));
		if (section.definition.examples) {
			if (section.definition.examples.length > 3)
				w.push(warn('DefinitionCard', 'examples max 3'));
			section.definition.examples.forEach((ex, i) => {
				if (words(ex) > 30)
					w.push(warn(`DefinitionCard example ${i + 1}`, 'exceeds 30 words'));
			});
		}
	}

	// Definition family
	if (section.definition_family) {
		if (section.definition_family.definitions.length > 4)
			w.push(warn('DefinitionFamily', 'definitions max 4'));
	}

	// Worked example(s)
	const examples = [
		...(section.worked_example ? [section.worked_example] : []),
		...(section.worked_examples ?? []),
	];
	examples.forEach((ex, ei) => {
		const label = `WorkedExampleCard[${ei}]`;
		if (ex.steps.length > 6) w.push(warn(label, 'steps max 6'));
		else if (ex.steps.length > 4)
			w.push(warn(label, `${ex.steps.length} steps — consider trimming (warning at 4)`));
		ex.steps.forEach((s, si) => {
			if (words(s.label) > 12)
				w.push(warn(`${label} step ${si + 1}`, 'label exceeds 12 words'));
			if (words(s.content) > 80)
				w.push(warn(`${label} step ${si + 1}`, 'content exceeds 80 words'));
		});
		if (ex.diagram) validateDiagram(ex.diagram, `${label}/diagram`, w);
	});

	// Process
	if (section.process) {
		if (section.process.steps.length > 8) w.push(warn('ProcessSteps', 'steps max 8'));
	}

	// Pitfall(s)
	const pitfalls = [
		...(section.pitfall ? [section.pitfall] : []),
		...(section.pitfalls ?? []),
	];
	pitfalls.forEach((p, i) => {
		if (words(p.misconception) > 20)
			w.push(warn(`PitfallAlert[${i}]`, 'misconception exceeds 20 words'));
		if (words(p.correction) > 80)
			w.push(warn(`PitfallAlert[${i}]`, 'correction exceeds 80 words'));
	});

	// Practice
	if (section.practice) {
		if (section.practice.problems.length < 2)
			w.push(warn('PracticeStack', 'minimum 2 problems'));
		if (section.practice.problems.length > 5)
			w.push(warn('PracticeStack', 'maximum 5 problems'));
		section.practice.problems.forEach((p, i) => {
			if (words(p.question) > 100)
				w.push(warn(`PracticeStack problem ${i + 1}`, 'question exceeds 100 words'));
			if (p.hints.length > 3)
				w.push(warn(`PracticeStack problem ${i + 1}`, 'hints max 3'));
			p.hints.forEach((h, hi) => {
				if (words(h.text) > 60)
					w.push(warn(`PracticeStack problem ${i + 1} hint ${hi + 1}`, 'hint exceeds 60 words'));
			});
			if (p.diagram) validateDiagram(p.diagram, `PracticeStack problem ${i + 1}/diagram`, w);
		});
	}

	// Insight strip
	if (section.insight_strip) {
		if (section.insight_strip.cells.length > 3)
			w.push(warn('InsightStrip', 'cells max 3'));
		if (section.insight_strip.cells.length < 2)
			w.push(warn('InsightStrip', 'cells min 2'));
	}

	if (section.comparison_grid) {
		validateComparisonGrid(section.comparison_grid, w);
	}

	// Glossary
	if (section.glossary) {
		if (section.glossary.terms.length > 8)
			w.push(warn('GlossaryRail', 'terms max 8'));
		else if (section.glossary.terms.length > 6)
			w.push(
				warn(
					'GlossaryRail',
					`${section.glossary.terms.length} terms — approaching limit (warning at 6)`
				)
			);
		section.glossary.terms.forEach((t, i) => {
			if (words(t.definition) > 30)
				w.push(warn(`GlossaryRail term ${i + 1}`, 'definition exceeds 30 words'));
		});
	}

	if (section.timeline) {
		validateTimeline(section.timeline, w);
	}

	// What next
	if (section.what_next) {
		if (words(section.what_next.body) > 50)
			w.push(warn('WhatNextBridge', 'body exceeds 50 words'));
		if (words(section.what_next.next) > 15) w.push(warn('WhatNextBridge', 'next exceeds 15 words'));
		if (section.what_next.preview && words(section.what_next.preview) > 30)
			w.push(warn('WhatNextBridge', 'preview exceeds 30 words'));
		if (section.what_next.prerequisites && section.what_next.prerequisites.length > 4)
			w.push(warn('WhatNextBridge', 'prerequisites max 4'));
	}

	if (section.interview) {
		if (words(section.interview.prompt) > 35)
			w.push(warn('InterviewAnchor', 'prompt exceeds 35 words'));
		if (words(section.interview.audience) > 10)
			w.push(warn('InterviewAnchor', 'audience exceeds 10 words'));
		if (section.interview.follow_up && words(section.interview.follow_up) > 25)
			w.push(warn('InterviewAnchor', 'follow_up exceeds 25 words'));
	}

	if (section.quiz) {
		if (words(section.quiz.question) > 60) w.push(warn('QuizCheck', 'question exceeds 60 words'));
		if (section.quiz.options.length < 3 || section.quiz.options.length > 4)
			w.push(warn('QuizCheck', 'options must be 3-4'));
		section.quiz.options.forEach((option, index) => {
			if (words(option.text) > 20)
				w.push(warn('QuizCheck', `option ${index + 1} text exceeds 20 words`));
			if (words(option.explanation) > 40)
				w.push(warn('QuizCheck', `option ${index + 1} explanation exceeds 40 words`));
		});
		if (words(section.quiz.feedback_correct) > 30)
			w.push(warn('QuizCheck', 'feedback_correct exceeds 30 words'));
		if (words(section.quiz.feedback_incorrect) > 30)
			w.push(warn('QuizCheck', 'feedback_incorrect exceeds 30 words'));
	}

	if (section.reflection) {
		if (words(section.reflection.prompt) > 40)
			w.push(warn('ReflectionPrompt', 'prompt exceeds 40 words'));
		if (section.reflection.space !== undefined && section.reflection.space > 6)
			w.push(warn('ReflectionPrompt', 'space exceeds 6 lines'));
	}

	if (section.diagram) {
		validateDiagram(section.diagram, 'DiagramBlock', w);
	}

	if (section.diagram_compare) {
		validateDiagramCompare(section.diagram_compare, w);
	}

	if (section.diagram_series) {
		validateDiagramSeries(section.diagram_series, w);
	}

	if (section.video_embed) {
		validateVideoEmbed(section.video_embed, w);
	}

	if (section.image_block) {
		validateImageBlock(section.image_block, w);
	}

	if (section.simulation) {
		validateSimulation(section.simulation, w);
	}

	return w;
}

// Call this in dev — shows warnings in console
export function warnIfInvalid(section: SectionContent): void {
	if (typeof window === 'undefined') return;
	const warnings = validateSection(section);
	if (warnings.length === 0) return;
	console.group('[Lectio] Content validation warnings');
	warnings.forEach((msg) => console.warn(msg));
	console.groupEnd();
}
