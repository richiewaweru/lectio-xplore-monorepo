import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { mount, unmount } from 'svelte';
import QuestionsView from './objects/QuestionsView.svelte';
import { validateStructure } from '../contract/validation';
import type { LectioDocument, QuestionsContent } from '../contract/document';

const css = readFileSync(join(process.cwd(), 'src/lib/print/base-print.css'), 'utf8');
const rule = (selector: string) => {
	const start = css.indexOf(selector + ' {');
	expect(start).toBeGreaterThan(-1);
	return css.slice(start, css.indexOf('}', start));
};
const text = (value: string) => [{ type: 'text' as const, value }];

const matchContent: QuestionsContent = {
	items: [
		{
			id: 'Q1',
			prompt: text('Match each input to its route.'),
			answer_lines: 0,
			match: {
				left: [text('water'), text('light')],
				right: [text('captured by the leaves'), text('comes up from the roots')]
			}
		}
	]
};

describe('Print key idea', () => {
	it('is tinted with a 1px border, 18pt bold, and keeps the tint with backgrounds off', () => {
		const block = rule('.lectio-aside--key_idea.lectio-aside');
		expect(block).toContain('background: #E4F0E8');
		expect(block).toContain('border: 1px solid #1B5E40');
		expect(block).toContain('print-color-adjust: exact');
		const body = rule('.lectio-aside--key_idea .lectio-aside-body');
		expect(body).toContain('font-size: 18pt');
		expect(body).toContain('font-weight: 700');
	});
});

describe('Print match-pairs', () => {
	it('renders numbered items and lettered answers in two columns with a match blank per item', () => {
		const target = document.createElement('div');
		const app = mount(QuestionsView, { target, props: { content: matchContent, role: 'practice' } });
		const left = [...target.querySelectorAll('.lectio-match-left .lectio-match-row')];
		const right = [...target.querySelectorAll('.lectio-match-right .lectio-match-row')];
		expect(left.map((row) => row.querySelector('.lectio-match-key')?.textContent)).toEqual(['1', '2']);
		expect(right.map((row) => row.querySelector('.lectio-match-key')?.textContent)).toEqual(['A', 'B']);
		expect(left.every((row) => row.querySelector('.lectio-match-blank'))).toBe(true);
		expect(right.some((row) => row.querySelector('.lectio-match-blank'))).toBe(false);
		expect(target.querySelectorAll('.lectio-answer-line')).toHaveLength(0);
		expect(target.textContent).toContain('water');
		expect(target.textContent).toContain('comes up from the roots');
		unmount(app);
	});

	it('draws the match blank with a border so it survives background graphics off', () => {
		expect(rule('.lectio-match-blank::after')).toContain('border-bottom: 1px solid');
	});

	it('is accepted by the document schema', () => {
		const doc: LectioDocument = {
			document_version: 2,
			contract_version: '1.0.0',
			id: 'match-schema',
			title: 'Match',
			language: 'en',
			metadata: {},
			sections: [
				{
					id: 's1',
					title: 'S',
					blocks: [
						{ id: 'Q1', object: 'questions', intent: 'check-understanding', position: 0, content: matchContent }
					]
				}
			]
		};
		expect(validateStructure(doc)).toEqual([]);
		const bad = structuredClone(doc);
		(bad.sections[0].blocks[0].content as QuestionsContent).items[0].match = { left: [], right: [] };
		expect(validateStructure(bad).length).toBeGreaterThan(0);
	});
});
