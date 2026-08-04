import type { BlockInstance } from 'lectio';

const COMPONENT_HEIGHT_MM: Record<string, number> = {
	'section-header': 35,
	'hook-hero': 50,
	'explanation-block': 60,
	'definition-card': 45,
	'definition-family': 70,
	'comparison-grid': 90,
	'worked-example-card': 80,
	'process-steps': 70,
	'practice-stack': 100,
	'quiz-check': 60,
	'reflection-prompt': 30,
	'student-textbox': 40,
	'short-answer': 35,
	'fill-in-blank': 35,
	'pitfall-alert': 40,
	'diagram-block': 80,
	'diagram-compare': 90,
	'diagram-series': 120,
	'timeline-block': 80,
	'image-block': 70,
	'callout-block': 35,
	'summary-block': 45,
	'key-fact': 25,
	'insight-strip': 30,
	'prerequisite-strip': 35,
	'what-next-bridge': 30,
	'section-divider': 10,
	'glossary-rail': 50,
	'interview-anchor': 30,
	'simulation-block': 60
};

const A4_PRINTABLE_HEIGHT_MM = 267;
const DEFAULT_HEIGHT_MM = 50;

export function estimatePageCount(blocks: BlockInstance[]): number {
	let totalMm = 0;
	for (const block of blocks) {
		totalMm += COMPONENT_HEIGHT_MM[block.component_id] ?? DEFAULT_HEIGHT_MM;
	}
	return Math.max(1, Math.ceil(totalMm / A4_PRINTABLE_HEIGHT_MM));
}

export type PageWarningLevel = 'none' | 'info' | 'warn';

export function pageWarningLevel(pageCount: number): PageWarningLevel {
	if (pageCount <= 4) return 'none';
	if (pageCount <= 6) return 'info';
	return 'warn';
}

export function pageWarningMessage(pageCount: number): string | null {
	if (pageCount <= 4) return null;
	if (pageCount <= 6) return `This lesson is approximately ${pageCount} A4 pages.`;
	return `This lesson is approximately ${pageCount} A4 pages - consider keeping it under 4 pages for student focus.`;
}
