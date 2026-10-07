import type { TeachingPlanBlockView, TeachingPlanView } from './teaching-plan-review';

export type MisconceptionView = { id: string; description: string; risk?: string };

const ACTION_PHRASES: Record<string, string> = {
	'select-one': 'choose one answer',
	'select-many': 'choose all the answers that apply',
	'complete-missing-values': 'fill in the missing values',
	'classify-items': 'sort items into groups',
	'match-pairs': 'match related pairs',
	'order-items': 'put items in order',
	'reconstruct-order': 'rebuild the order of steps',
	'enter-number': 'work out and enter a number',
	'enter-text': 'write a short answer',
	'compare-without-response': 'compare examples',
	'read-explanation': 'read an explanation'
};

export function humanizeAction(action: string): string {
	return ACTION_PHRASES[action] ?? action.replaceAll('-', ' ');
}

/** "Learners will..." phrase from a block's learner action, or null when there is none. */
export function learnerActionPhrase(block: TeachingPlanBlockView): string | null {
	const action = block.learner_action;
	if (!action?.action) return null;
	const verb = humanizeAction(action.action);
	const target = action.target?.trim();
	return target ? `${verb}: ${target}` : verb;
}

export function sectionLearnerActions(blocks: TeachingPlanBlockView[] | undefined): string[] {
	const seen = new Set<string>();
	for (const block of blocks ?? []) {
		const phrase = learnerActionPhrase(block);
		if (phrase) seen.add(phrase);
	}
	return [...seen];
}

export function sectionFigureNotes(blocks: TeachingPlanBlockView[] | undefined): string[] {
	return (blocks ?? []).map((block) => block.visual?.purpose?.trim() ?? '').filter(Boolean);
}

export function resolveMisconceptions(
	ids: string[] | undefined,
	known: MisconceptionView[] | undefined
): MisconceptionView[] {
	const byId = new Map((known ?? []).map((item) => [item.id, item]));
	const out: MisconceptionView[] = [];
	for (const id of ids ?? []) {
		const hit = byId.get(id);
		if (hit?.description?.trim()) out.push(hit);
	}
	return out;
}

export function sectionTitle(
	section: NonNullable<TeachingPlanView['sections']>[number],
	index: number
): string {
	return section.display_title?.trim() || section.specific_purpose?.trim() || `Section ${index + 1}`;
}
