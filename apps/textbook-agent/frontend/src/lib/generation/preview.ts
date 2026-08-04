import type { SectionContent } from 'lectio';

function firstSentences(text: string, count = 2): string {
	const normalized = text.replace(/\s+/g, ' ').trim();
	if (!normalized) {
		return '';
	}

	const sentences = normalized.match(/[^.!?]+[.!?]?/g) ?? [normalized];
	return sentences
		.slice(0, count)
		.map((sentence) => sentence.trim())
		.join(' ')
		.trim();
}

export function buildSectionPreview(section: SectionContent): string {
	const textParts = [
		section.hook?.body,
		section.explanation?.body,
		section.definition?.plain,
		section.process?.intro,
		section.process?.steps?.[0]?.detail,
		section.process?.steps?.[0]?.action,
		section.practice?.problems?.[0]?.question,
		section.quiz?.question,
		section.reflection?.prompt,
		section.what_next?.body,
		section.what_next?.preview
	].filter((value): value is string => Boolean(value?.trim()));

	const preview = firstSentences(textParts.join(' '), 2);
	if (preview) {
		return preview;
	}

	return 'Section content is ready to read in the full lesson view.';
}
