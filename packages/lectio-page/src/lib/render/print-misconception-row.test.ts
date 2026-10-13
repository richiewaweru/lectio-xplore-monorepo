import { describe, expect, it } from 'vitest';
import { mount, unmount } from 'svelte';
import AsideView from './objects/AsideView.svelte';
import type { AsideContent } from '../contract/document';
import WorkedExampleView from './objects/WorkedExampleView.svelte';
import ChoicesView from './objects/ChoicesView.svelte';
import QuestionsView from './objects/QuestionsView.svelte';

const content: AsideContent = {
	label: 'Common misconception',
	body: 'unused',
	variant: 'misconception',
	belief: 'Heavier things fall faster.',
	evidence: 'In a vacuum a <strong>feather</strong> and a hammer land together.',
	conclusion: 'Air resistance, not weight, causes <em>the difference we see</em> in fall.'
};

describe('Print misconception rows', () => {
	it('keeps each row to a label and one text wrapper so inline markup cannot become grid items', () => {
		const target = document.createElement('div');
		const app = mount(AsideView, { target, props: { content, spanning: true } });
		const rows = [...target.querySelectorAll('.lectio-misconception-row')];
		expect(rows).toHaveLength(3);
		for (const row of rows) {
			expect(row.children).toHaveLength(2);
			const strayText = [...row.childNodes].filter(
				(node) => node.nodeType === Node.TEXT_NODE && (node.textContent ?? '').trim() !== ''
			);
			expect(strayText).toHaveLength(0);
		}
		const evidence = rows[1].querySelector('.lectio-misconception-text');
		const conclusion = rows[2].querySelector('.lectio-misconception-text');
		expect(evidence?.querySelector('strong')?.textContent).toBe('feather');
		expect(conclusion?.querySelector('em')?.textContent).toBe('the difference we see');
		unmount(app);
	});
});

function strayText(parent: Element) {
	return [...parent.childNodes].filter(
		(node) => node.nodeType === Node.TEXT_NODE && (node.textContent ?? '').trim() !== ''
	);
}

function expectWrapped(target: HTMLElement, parentSelector: string, wrapperClass: string, emText: string) {
	const parents = [...target.querySelectorAll(parentSelector)];
	expect(parents.length).toBeGreaterThan(0);
	const wrappers = parents.flatMap((parent) => [...parent.querySelectorAll(`:scope > span.${wrapperClass}`)]);
	expect(wrappers.length).toBeGreaterThan(0);
	for (const parent of parents) expect(strayText(parent)).toHaveLength(0);
	const wrapperWithEm = wrappers.find((w) => w.querySelector('em')?.textContent === emText);
	expect(wrapperWithEm).toBeDefined();
	expect(wrapperWithEm?.parentElement?.querySelector(':scope > em')).toBeNull();
}

describe('Inline text wrappers keep inline markup out of grid/flex items', () => {
	it('wraps worked example step and answer text', () => {
		const target = document.createElement('div');
		const app = mount(WorkedExampleView, {
			target,
			props: {
				content: {
					problem: 'Solve it.',
					steps: [{ text: 'Apply <em>the rule</em> first.' }],
					answer: 'It is <em>forty-two</em>.'
				}
			}
		});
		expectWrapped(target, '.lectio-step', 'lectio-step-text', 'the rule');
		const steps = [...target.querySelectorAll('.lectio-step')];
		expect(steps).toHaveLength(2);
		expect(steps[1].querySelector(':scope > span.lectio-step-text em')?.textContent).toBe('forty-two');
		unmount(app);
	});

	it('wraps choice option text', () => {
		const target = document.createElement('div');
		const app = mount(ChoicesView, {
			target,
			props: {
				content: {
					stem: 'Pick one.',
					options: [
						{ letter: 'A', text: 'The <em>first</em> option' },
						{ letter: 'B', text: 'Plain option' }
					]
				}
			}
		});
		expectWrapped(target, '.lectio-choice', 'lectio-choice-text', 'first');
		unmount(app);
	});

	it('wraps the task prompt', () => {
		const target = document.createElement('div');
		const app = mount(QuestionsView, {
			target,
			props: {
				content: { items: [{ id: 'Q1', prompt: 'Explain <em>why</em> it works.' }] }
			}
		});
		expectWrapped(target, '.lectio-task-body', 'lectio-task-prompt', 'why');
		unmount(app);
	});

	it('wraps non-key_idea aside body', () => {
		const target = document.createElement('div');
		const app = mount(AsideView, {
			target,
			props: { content: { body: 'Remember <em>this</em> note.', variant: 'note' } as AsideContent }
		});
		expectWrapped(target, 'aside.lectio-aside', 'lectio-aside-text', 'this');
		unmount(app);
	});
});
