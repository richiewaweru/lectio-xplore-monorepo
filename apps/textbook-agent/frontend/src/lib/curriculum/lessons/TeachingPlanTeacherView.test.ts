// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import TeachingPlanTeacherView from './TeachingPlanTeacherView.svelte';
import TeachingPlanDraft from './TeachingPlanDraft.svelte';
import type { TeachingPlanView } from './teaching-plan-review';

const plan: TeachingPlanView = {
	revision: 3,
	contract_version: 2,
	arc: 'Move from guessing to measuring.',
	learner_title: 'Finding the area of a garden',
	starting_state: ['Can multiply whole numbers.'],
	target_state: ['Explain why area is length times width.'],
	misconception_focus_ids: ['m-perimeter', 'm-unknown'],
	sections: [
		{
			slot_id: 'slot-orient-9',
			display_title: 'Start with the garden',
			specific_purpose: 'Learners notice that covering a bed needs a number.',
			entry_state: ['entry-state-text'],
			must_establish: ['must-establish-text'],
			avoid_repeating: ['avoid-repeating-text'],
			exit_state: ['exit-state-text'],
			blocks: [
				{
					id: 'block-id-77',
					intent: 'orient',
					brief: 'Show the bed.',
					evidence: 'ok',
					evidence_refs: ['evidence-ref-5'],
					departure_reason: 'departure-reason-text',
					visual: { purpose: 'Garden bed with sides labelled' },
					learner_action: {
						action: 'enter-number',
						target: 'the area',
						purpose: 'p',
						expected_evidence: 'e',
						difficulty: 'guided'
					}
				}
			]
		},
		{ slot_id: 'slot-two', display_title: null, specific_purpose: 'Practise with new sizes.', blocks: [] }
	]
};
const identity = { revision: 3, pending_hash_verified: true, pending_content_hash: 'hash-secret-1' };
const misconceptions = [{ id: 'm-perimeter', description: 'Area is the same as perimeter.', risk: 'high' }];

describe('TeachingPlanTeacherView', () => {
	afterEach(cleanup);

	function mount() {
		return render(TeachingPlanTeacherView, {
			props: {
				plan,
				review: { status: 'pending', revision: 3 },
				identity,
				misconceptions,
				backbone: {
					anchor: { id: 'a', story: 'A bed is 6 m by 4 m.', data: {}, answer: null, figure_ids: [] },
					variants: [],
					figures: []
				}
			}
		});
	}

	it('shows teacher-facing content with misconceptions resolved to text', () => {
		const { container } = mount();
		const text = container.textContent ?? '';
		expect(screen.getByRole('heading', { name: 'Finding the area of a garden' })).toBeTruthy();
		expect(text).toContain('Explain why area is length times width.');
		expect(text).toContain('Can multiply whole numbers.');
		expect(text).toContain('A bed is 6 m by 4 m.');
		expect(text).toContain('Area is the same as perimeter.');
		expect(text).not.toContain('m-perimeter');
		expect(text).not.toContain('m-unknown');
		expect(screen.getByRole('heading', { name: 'Start with the garden' })).toBeTruthy();
		expect(text).toContain('Learners notice that covering a bed needs a number.');
		expect(text).toContain('work out and enter a number: the area');
		expect(text).toContain('Figure: Garden bed with sides labelled');
		// falls back to the purpose, never the raw slot id
		expect(screen.getByRole('heading', { name: 'Practise with new sizes.' })).toBeTruthy();
		expect(text).not.toContain('slot-two');
	});

	it('hides jargon and the full plan until inspected', async () => {
		const { container } = mount();
		for (const hidden of [
			'slot-orient-9', 'must-establish-text', 'avoid-repeating-text', 'entry-state-text',
			'block-id-77', 'evidence-ref-5', 'hash-secret-1', 'departure-reason-text'
		]) {
			expect(container.textContent).not.toContain(hidden);
		}
		await fireEvent.click(screen.getByRole('button', { name: 'Inspect full plan' }));
		expect(container.textContent).toContain('must-establish-text');
		expect(container.textContent).toContain('evidence-ref-5');
		expect(container.textContent).toContain('departure-reason-text');
		expect(container.textContent).toContain('hash-secret-1');
		await fireEvent.click(screen.getByRole('button', { name: 'Hide full plan' }));
		expect(container.textContent).not.toContain('hash-secret-1');
	});
});

describe('TeachingPlanDraft', () => {
	afterEach(cleanup);

	it('renders numbered section cards, streaming the pending ones, without block intent ids', () => {
		const { container } = render(TeachingPlanDraft, {
			props: {
				draft: {
					status: 'draft',
					spine: {
						learner_title: 'Water in plants',
						arc: 'Follow the water.',
						sections: [
							{ slot_id: 's1', display_title: 'Watch the leaf', specific_purpose: 'See droplets form.' },
							{ slot_id: 's2', display_title: 'Explain it', specific_purpose: 'Say why.' }
						]
					},
					sections: {
						s1: { unresolved: false, blocks: [{ intent: 'orient-intent-x', brief: 'Cover a leaf.', task_mode: 'learn', has_visual: true }] }
					},
					ready_sections: ['s1'],
					total_sections: 2
				}
			}
		});
		const text = container.textContent ?? '';
		expect(text).toContain('Water in plants');
		expect(text).toContain('Watch the leaf');
		expect(text).toContain('Cover a leaf.');
		expect(text).toContain('Writing this section…');
		expect(text).not.toContain('orient-intent-x');
		expect(text).not.toContain('s1');
		expect(container.querySelectorAll('li.card').length).toBe(2);
	});
});
