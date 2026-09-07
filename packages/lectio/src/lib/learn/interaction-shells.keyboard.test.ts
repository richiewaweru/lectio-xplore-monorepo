/**
 * Isolated keyboard / shell tests — import only learn shells, not templates.
 */
import { describe, expect, it } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import ChoiceInteraction from './ChoiceInteraction.svelte';
import SequenceInteraction from './SequenceInteraction.svelte';
import MatchPairsInteraction from './MatchPairsInteraction.svelte';
import NumericInteraction from './NumericInteraction.svelte';
import ShortResponseInteraction from './ShortResponseInteraction.svelte';
import ClassifyInteraction from './ClassifyInteraction.svelte';
import ImageHotspotInteraction from './ImageHotspotInteraction.svelte';
import {
	evaluateChoice,
	evaluateMatchPairs,
	evaluateSequence,
	evaluateNumeric,
	evaluateFillBlank,
	validateInteractionContract,
	type LearnInteractionContract
} from './interaction-contract';

const feedback = {
	correct: 'Correct',
	incorrect: 'Incorrect',
	partial: 'Partial'
};

describe('interaction shell evaluators (per kind)', () => {
	it('choice / image-choice correct and incorrect', () => {
		expect(
			evaluateChoice({ correct_option_id: 'b' }, { selected_option_id: 'b' }, feedback).outcome
		).toBe('correct');
		expect(
			evaluateChoice({ correct_option_id: 'b' }, { selected_option_id: 'a' }, feedback).outcome
		).toBe('incorrect');
	});

	it('match / classify / drag-label partial', () => {
		const config = {
			pairs: [
				{ left: '1', right: 'a' },
				{ left: '2', right: 'b' }
			]
		};
		expect(
			evaluateMatchPairs(config, { matches: [{ left: '1', right: 'a' }] }, feedback).outcome
		).toBe('partial');
		expect(
			evaluateMatchPairs(
				config,
				{
					matches: [
						{ left: '1', right: 'a' },
						{ left: '2', right: 'b' }
					]
				},
				feedback
			).outcome
		).toBe('correct');
	});

	it('sequence correct/incorrect', () => {
		expect(
			evaluateSequence({ order: ['a', 'b', 'c'] }, { order: ['a', 'b', 'c'] }, feedback).outcome
		).toBe('correct');
		const reversed = evaluateSequence(
			{ order: ['a', 'b', 'c'] },
			{ order: ['c', 'b', 'a'] },
			feedback
		);
		expect(['incorrect', 'partial']).toContain(reversed.outcome);
		expect(reversed.outcome).not.toBe('correct');
	});

	it('numeric / short-response / fill-blank', () => {
		expect(evaluateNumeric({ value: 10, tolerance: 1 }, { value: 10.5 }, feedback).outcome).toBe(
			'correct'
		);
		expect(evaluateFillBlank({ answers: ['CO2'] }, { blanks: ['co2'] }, feedback).outcome).toBe(
			'correct'
		);
	});

	it('validates config-only contracts for new kinds', () => {
		const kinds: LearnInteractionContract['kind'][] = [
			'match-pairs',
			'classify',
			'sequence',
			'numeric',
			'image-hotspot',
			'drag-label'
		];
		for (const kind of kinds) {
			const contract: LearnInteractionContract = {
				id: kind,
				kind,
				prompt: 'p',
				assessment_mode: 'practice',
				attempt_policy: {
					max_attempts: 2,
					show_feedback_after_submit: true,
					allow_retry_after_correct: false
				},
				feedback,
				completion: { type: 'submitted' },
				config:
					kind === 'sequence'
						? { order: ['a'] }
						: kind === 'numeric'
							? { value: 1 }
							: kind === 'match-pairs' || kind === 'classify' || kind === 'drag-label'
								? { pairs: [{ left: 'a', right: 'b' }] }
								: { correct_option_id: 'x' },
				accessibility: { keyboard_operable: true },
				ai_config_rule: 'config-only'
			};
			expect(validateInteractionContract(contract)).toEqual([]);
		}
	});
});

describe('interaction shell keyboard operability', () => {
	it('ChoiceInteraction selects via Enter/Space', async () => {
		const { getByRole, getByText } = render(ChoiceInteraction, {
			props: {
				prompt: 'Pick one',
				options: [
					{ id: 'a', text: 'Alpha' },
					{ id: 'b', text: 'Beta' }
				],
				correctOptionId: 'b',
				feedback
			}
		});
		const beta = getByRole('radio', { name: 'Beta' });
		await fireEvent.keyDown(beta, { key: 'Enter' });
		await fireEvent.click(getByRole('button', { name: 'Check' }));
		expect(getByText('Correct')).toBeTruthy();
	});

	it('SequenceInteraction moves items with buttons', async () => {
		const { getByLabelText, getByRole, getByText } = render(SequenceInteraction, {
			props: {
				prompt: 'Order',
				steps: [
					{ id: 'b', label: 'Second' },
					{ id: 'a', label: 'First' }
				],
				correctOrder: ['a', 'b'],
				feedback
			}
		});
		await fireEvent.click(getByLabelText('Move Second down'));
		await fireEvent.click(getByRole('button', { name: 'Check' }));
		expect(getByText('Correct')).toBeTruthy();
	});

	it('MatchPairsInteraction pairs via keyboard', async () => {
		const { getByRole, getByText } = render(MatchPairsInteraction, {
			props: {
				prompt: 'Match',
				left: [{ id: '1', label: 'Left1' }],
				right: [{ id: 'a', label: 'RightA' }],
				correctPairs: [{ left: '1', right: 'a' }],
				feedback
			}
		});
		const left = getByRole('button', { name: 'Left1' });
		await fireEvent.keyDown(left, { key: ' ' });
		const right = getByRole('button', { name: 'RightA' });
		await fireEvent.keyDown(right, { key: 'Enter' });
		await fireEvent.click(getByRole('button', { name: 'Check' }));
		expect(getByText('Correct')).toBeTruthy();
	});

	it('NumericInteraction submits from Check', async () => {
		const { getByLabelText, getByRole, getByText } = render(NumericInteraction, {
			props: {
				prompt: 'Value?',
				value: 42,
				tolerance: 0,
				feedback
			}
		});
		await fireEvent.input(getByLabelText('Answer'), { target: { value: '42' } });
		await fireEvent.click(getByRole('button', { name: 'Check' }));
		expect(getByText('Correct')).toBeTruthy();
	});

	it('ShortResponseInteraction submits on Enter', async () => {
		const { getByLabelText, getByText } = render(ShortResponseInteraction, {
			props: {
				prompt: 'Name the gas',
				acceptedAnswers: ['CO2', 'carbon dioxide'],
				feedback
			}
		});
		const input = getByLabelText('Answer');
		await fireEvent.input(input, { target: { value: 'CO2' } });
		await fireEvent.keyDown(input, { key: 'Enter' });
		expect(getByText('Correct')).toBeTruthy();
	});

	it('ClassifyInteraction assigns with keyboard', async () => {
		const { getByRole, getByText } = render(ClassifyInteraction, {
			props: {
				prompt: 'Classify',
				items: [{ id: 'apple', label: 'Apple' }],
				categories: [{ id: 'fruit', label: 'Fruit' }],
				correctPairs: [{ left: 'apple', right: 'fruit' }],
				feedback
			}
		});
		await fireEvent.keyDown(getByRole('button', { name: 'Apple' }), { key: 'Enter' });
		await fireEvent.keyDown(getByRole('button', { name: 'Fruit' }), { key: ' ' });
		await fireEvent.click(getByRole('button', { name: 'Check' }));
		expect(getByText('Correct')).toBeTruthy();
	});

	it('ImageHotspotInteraction is keyboard focusable', async () => {
		const { getByLabelText, getByRole, getByText } = render(ImageHotspotInteraction, {
			props: {
				prompt: 'Click the leaf',
				imageUrl: 'data:image/gif;base64,R0lGODlhAQABAAAAACw=',
				imageAlt: 'diagram',
				hotspots: [
					{ id: 'leaf', label: 'Leaf', x: 40, y: 40 },
					{ id: 'root', label: 'Root', x: 60, y: 80 }
				],
				correctOptionId: 'leaf',
				feedback
			}
		});
		const leaf = getByLabelText('Leaf');
		await fireEvent.click(leaf);
		await fireEvent.click(getByRole('button', { name: 'Check' }));
		expect(getByText('Correct')).toBeTruthy();
	});
});
