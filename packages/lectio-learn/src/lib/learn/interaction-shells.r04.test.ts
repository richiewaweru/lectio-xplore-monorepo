/**
 * R04-G05 — offline rendering evidence: mount @lectio/learn shells with envelope-shaped
 * contracts (prompt + config + feedback). MOCK provider output shape; real component mount.
 */
import { describe, expect, it } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import ChoiceInteraction from './ChoiceInteraction.svelte';
import MultiSelectInteraction from './MultiSelectInteraction.svelte';
import SequenceInteraction from './SequenceInteraction.svelte';
import MatchPairsInteraction from './MatchPairsInteraction.svelte';
import NumericInteraction from './NumericInteraction.svelte';
import ShortResponseInteraction from './ShortResponseInteraction.svelte';
import ClassifyInteraction from './ClassifyInteraction.svelte';
import {
	validateInteractionContract,
	type LearnInteractionContract,
	type FeedbackSpec
} from './interaction-contract';

const feedback: FeedbackSpec = {
	correct: 'Correct',
	incorrect: 'Incorrect',
	partial: 'Partial'
};

/** Envelope-shaped contract as produced by Learn authoring adapter (config-only rule). */
function envelopeContract(
	kind: LearnInteractionContract['kind'],
	config: Record<string, unknown>,
	prompt: string
): LearnInteractionContract {
	return {
		id: `r04-${kind}`,
		kind,
		prompt,
		assessment_mode: 'graded',
		attempt_policy: {
			max_attempts: 2,
			show_feedback_after_submit: true,
			allow_retry_after_correct: false
		},
		feedback,
		completion: { type: 'submitted' },
		config,
		accessibility: { keyboard_operable: true },
		ai_config_rule: 'config-only'
	};
}

describe('R04-G05 offline rendering — eight core interactions', () => {
	const kinds: LearnInteractionContract['kind'][] = [
		'choice',
		'multi-select',
		'fill-blank',
		'numeric',
		'short-response',
		'match-pairs',
		'classify',
		'sequence'
	];

	it('validates envelope contracts for all eight core kinds', () => {
		const configs: Record<string, Record<string, unknown>> = {
			choice: {
				options: [
					{ id: 'a', text: 'A' },
					{ id: 'b', text: 'B' }
				],
				correct_option_id: 'b'
			},
			'multi-select': {
				options: [
					{ id: 'a', text: 'A' },
					{ id: 'b', text: 'B' },
					{ id: 'c', text: 'C' }
				],
				correct_option_ids: ['a', 'c']
			},
			'fill-blank': { answers: ['chlorophyll'], blank_ids: ['pigment'], case_sensitive: false },
			numeric: { value: 50, tolerance: 0, unit: 'm' },
			'short-response': { evaluation: 'teacher-review', review_guidance: 'Explain.' },
			'match-pairs': { pairs: [{ left: 'lit', right: 'food' }] },
			classify: {
				categories: [{ id: 'in', label: 'Input' }],
				pairs: [{ left: 'light', right: 'in' }]
			},
			sequence: {
				items: [
					{ id: 'a', label: 'First' },
					{ id: 'b', label: 'Second' }
				],
				order: ['a', 'b']
			}
		};
		for (const kind of kinds) {
			const contract = envelopeContract(kind, configs[kind]!, `Prompt for ${kind}`);
			expect(validateInteractionContract(contract)).toEqual([]);
		}
	});

	it('choice — mount, submit correct via keyboard', async () => {
		const c = envelopeContract(
			'choice',
			{
				options: [
					{ id: 'a', text: 'No light' },
					{ id: 'b', text: 'Light required' }
				],
				correct_option_id: 'b'
			},
			'Why did the covered leaf fail?'
		);
		const { getByRole, getByText } = render(ChoiceInteraction, {
			props: {
				prompt: c.prompt,
				options: c.config.options as { id: string; text: string }[],
				correctOptionId: c.config.correct_option_id as string,
				feedback: c.feedback
			}
		});
		await fireEvent.keyDown(getByRole('radio', { name: 'Light required' }), { key: 'Enter' });
		await fireEvent.click(getByRole('button', { name: 'Check' }));
		expect(getByText('Correct')).toBeTruthy();
	});

	it('multi-select — mount, submit correct', async () => {
		const c = envelopeContract(
			'multi-select',
			{
				options: [
					{ id: 'light', text: 'light' },
					{ id: 'co2', text: 'CO2' },
					{ id: 'noise', text: 'noise' }
				],
				correct_option_ids: ['light', 'co2']
			},
			'Select inputs for photosynthesis'
		);
		const { getByRole, getByText } = render(MultiSelectInteraction, {
			props: {
				prompt: c.prompt,
				options: c.config.options as { id: string; text: string }[],
				correctOptionIds: c.config.correct_option_ids as string[],
				feedback: c.feedback
			}
		});
		await fireEvent.click(getByRole('button', { name: 'light' }));
		await fireEvent.click(getByRole('button', { name: 'CO2' }));
		await fireEvent.click(getByRole('button', { name: 'Check' }));
		expect(getByText('Correct')).toBeTruthy();
	});

	it('fill-blank — single blank via ShortResponse shell', async () => {
		const c = envelopeContract(
			'fill-blank',
			{ answers: ['chlorophyll'], blank_ids: ['pigment'], case_sensitive: false },
			'Name the green pigment'
		);
		const { getByLabelText, getByText } = render(ShortResponseInteraction, {
			props: {
				prompt: c.prompt,
				acceptedAnswers: c.config.answers as string[],
				feedback: c.feedback
			}
		});
		await fireEvent.input(getByLabelText('Answer'), { target: { value: 'chlorophyll' } });
		await fireEvent.keyDown(getByLabelText('Answer'), { key: 'Enter' });
		expect(getByText('Correct')).toBeTruthy();
	});

	it('numeric — mount and submit', async () => {
		const c = envelopeContract('numeric', { value: 50, tolerance: 0, unit: 'm' }, 'How far?');
		const { getByLabelText, getByRole, getByText } = render(NumericInteraction, {
			props: {
				prompt: c.prompt,
				value: c.config.value as number,
				tolerance: c.config.tolerance as number,
				feedback: c.feedback
			}
		});
		await fireEvent.input(getByLabelText('Answer'), { target: { value: '50' } });
		await fireEvent.click(getByRole('button', { name: 'Check' }));
		expect(getByText('Correct')).toBeTruthy();
	});

	it('short-response — mount and submit', async () => {
		const c = envelopeContract(
			'short-response',
			{ evaluation: 'teacher-review', review_guidance: 'Explain light.' },
			'Explain why light is required'
		);
		const { getByLabelText, getByText } = render(ShortResponseInteraction, {
			props: {
				prompt: c.prompt,
				acceptedAnswers: ['light'],
				feedback: c.feedback
			}
		});
		await fireEvent.input(getByLabelText('Answer'), { target: { value: 'light' } });
		await fireEvent.keyDown(getByLabelText('Answer'), { key: 'Enter' });
		expect(getByText('Correct')).toBeTruthy();
	});

	it('match-pairs — mount and submit', async () => {
		const pairs = [{ left: 'lit', right: 'food' }];
		const c = envelopeContract('match-pairs', { pairs }, 'Match conditions');
		const { getByRole, getByText } = render(MatchPairsInteraction, {
			props: {
				prompt: c.prompt,
				left: [{ id: 'lit', label: 'lit' }],
				right: [{ id: 'food', label: 'food' }],
				correctPairs: pairs,
				feedback: c.feedback
			}
		});
		await fireEvent.keyDown(getByRole('button', { name: 'lit' }), { key: ' ' });
		await fireEvent.keyDown(getByRole('button', { name: 'food' }), { key: 'Enter' });
		await fireEvent.click(getByRole('button', { name: 'Check' }));
		expect(getByText('Correct')).toBeTruthy();
	});

	it('classify — mount and submit', async () => {
		const c = envelopeContract(
			'classify',
			{
				categories: [{ id: 'input', label: 'Input' }],
				pairs: [{ left: 'light', right: 'input' }]
			},
			'Classify inputs'
		);
		const { getByRole, getByText } = render(ClassifyInteraction, {
			props: {
				prompt: c.prompt,
				items: [{ id: 'light', label: 'light' }],
				categories: [{ id: 'input', label: 'Input' }],
				correctPairs: [{ left: 'light', right: 'input' }],
				feedback: c.feedback
			}
		});
		await fireEvent.keyDown(getByRole('button', { name: 'light' }), { key: 'Enter' });
		await fireEvent.keyDown(getByRole('button', { name: 'Input' }), { key: ' ' });
		await fireEvent.click(getByRole('button', { name: 'Check' }));
		expect(getByText('Correct')).toBeTruthy();
	});

	it('sequence — mount and submit', async () => {
		const c = envelopeContract(
			'sequence',
			{
				items: [
					{ id: 'b', label: 'Second' },
					{ id: 'a', label: 'First' }
				],
				order: ['a', 'b']
			},
			'Order the stages'
		);
		const items = c.config.items as { id: string; label: string }[];
		const { getByLabelText, getByRole, getByText } = render(SequenceInteraction, {
			props: {
				prompt: c.prompt,
				steps: items,
				correctOrder: c.config.order as string[],
				feedback: c.feedback
			}
		});
		await fireEvent.click(getByLabelText('Move Second down'));
		await fireEvent.click(getByRole('button', { name: 'Check' }));
		expect(getByText('Correct')).toBeTruthy();
	});
});
