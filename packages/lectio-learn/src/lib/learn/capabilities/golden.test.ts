// @vitest-environment node

/**
 * Golden evaluator tests for every activated interaction kind.
 *
 * "Golden" here means the expected outcome is stated, not inferred: each case
 * fixes a config, a response and the exact result. The negative half matters
 * more than the positive half — a malformed config must fail as an authoring
 * error, and an impossible response must fail rather than be scored, because a
 * scored impossible response is fabricated evidence.
 */

import { describe, expect, it } from 'vitest';

import {
	createAttemptState,
	evaluateInteraction,
	InteractionConfigError,
	InteractionResponseError,
	recordAttempt,
	validateInteractionContract,
	type InteractionKindId,
	type LearnInteractionContract
} from '$lib/learn/interaction-contract';
import { capabilityById, learnCapabilities } from './index';

const FEEDBACK = { correct: 'Yes.', incorrect: 'Not yet.', partial: 'Partly.' };

function contract(
	kind: InteractionKindId,
	config: Record<string, unknown>,
	overrides: Partial<LearnInteractionContract> = {}
): LearnInteractionContract {
	return {
		id: `golden-${kind}`,
		kind,
		prompt: 'Golden prompt',
		assessment_mode: 'graded',
		attempt_policy: {
			max_attempts: 2,
			show_feedback_after_submit: true,
			allow_retry_after_correct: false
		},
		feedback: FEEDBACK,
		completion: { type: 'correct' },
		config,
		accessibility: { keyboard_operable: true },
		ai_config_rule: 'config-only',
		...overrides
	};
}

const CHOICE_CONFIG = {
	options: [
		{ id: 'a', text: 'A' },
		{ id: 'b', text: 'B' },
		{ id: 'c', text: 'C' }
	],
	correct_option_id: 'b'
};

describe('golden: choice', () => {
	it('scores the declared correct option and nothing else', () => {
		const c = contract('choice', CHOICE_CONFIG);
		expect(evaluateInteraction(c, { selected_option_id: 'b' })).toMatchObject({
			outcome: 'correct',
			score_earned: 1,
			score_possible: 1
		});
		expect(evaluateInteraction(c, { selected_option_id: 'a' })).toMatchObject({
			outcome: 'incorrect',
			score_earned: 0
		});
	});

	it('rejects a selection that is not a declared option', () => {
		const c = contract('choice', CHOICE_CONFIG);
		expect(() => evaluateInteraction(c, { selected_option_id: 'zzz' })).toThrow(
			InteractionResponseError
		);
	});

	it('rejects an empty selection rather than scoring it incorrect', () => {
		const c = contract('choice', CHOICE_CONFIG);
		expect(() => evaluateInteraction(c, { selected_option_id: '' })).toThrow(
			InteractionResponseError
		);
	});

	it('rejects a correct_option_id that is not among the options', () => {
		const c = contract('choice', { ...CHOICE_CONFIG, correct_option_id: 'missing' });
		expect(() => evaluateInteraction(c, { selected_option_id: 'a' })).toThrow(
			InteractionConfigError
		);
	});

	it('rejects duplicate option ids at validation time', () => {
		const errors = validateInteractionContract(
			contract('choice', {
				options: [
					{ id: 'a', text: 'A' },
					{ id: 'a', text: 'Also A' }
				],
				correct_option_id: 'a'
			})
		);
		expect(errors.join('\n')).toMatch(/unique|duplicate/i);
	});
});

describe('golden: multi-select', () => {
	const config = {
		options: [
			{ id: 'a', text: 'A' },
			{ id: 'b', text: 'B' },
			{ id: 'c', text: 'C' },
			{ id: 'd', text: 'D' }
		],
		correct_option_ids: ['a', 'c']
	};

	it('awards partial credit for a subset and penalises a false positive', () => {
		const c = contract('multi-select', config);
		expect(evaluateInteraction(c, { selected_option_ids: ['a', 'c'] })).toMatchObject({
			outcome: 'correct',
			score_earned: 2,
			score_possible: 2
		});
		expect(evaluateInteraction(c, { selected_option_ids: ['a'] })).toMatchObject({
			outcome: 'partial',
			score_earned: 1,
			score_possible: 2
		});
		// One hit, one false positive: the false positive cancels the hit.
		expect(evaluateInteraction(c, { selected_option_ids: ['a', 'd'] })).toMatchObject({
			outcome: 'incorrect',
			score_earned: 0
		});
	});

	it('rejects duplicate ids in the response', () => {
		const c = contract('multi-select', config);
		expect(() => evaluateInteraction(c, { selected_option_ids: ['a', 'a'] })).toThrow(
			InteractionResponseError
		);
	});

	it('rejects an unknown id in the response', () => {
		const c = contract('multi-select', config);
		expect(() => evaluateInteraction(c, { selected_option_ids: ['a', 'zzz'] })).toThrow(
			InteractionResponseError
		);
	});

	it('rejects a correct id that is not a declared option', () => {
		const c = contract('multi-select', { ...config, correct_option_ids: ['a', 'zzz'] });
		expect(() => evaluateInteraction(c, { selected_option_ids: ['a'] })).toThrow(
			InteractionConfigError
		);
	});
});

describe('golden: fill-blank', () => {
	const config = {
		answers: [['CO2', 'carbon dioxide'], 'water'],
		blank_ids: ['b1', 'b2']
	};

	it('accepts a declared alternative and normalises case and whitespace', () => {
		const c = contract('fill-blank', config);
		expect(
			evaluateInteraction(c, { blanks: ['  carbon   dioxide ', 'WATER'] })
		).toMatchObject({ outcome: 'correct', score_earned: 2, score_possible: 2 });
	});

	it('awards partial credit per blank', () => {
		const c = contract('fill-blank', config);
		expect(evaluateInteraction(c, { blanks: ['CO2', 'soil'] })).toMatchObject({
			outcome: 'partial',
			score_earned: 1,
			score_possible: 2
		});
	});

	it('rejects a response with the wrong number of blanks', () => {
		const c = contract('fill-blank', config);
		expect(() => evaluateInteraction(c, { blanks: ['CO2'] })).toThrow(InteractionResponseError);
	});

	it('rejects blank_ids that do not match the answer count', () => {
		const c = contract('fill-blank', { ...config, blank_ids: ['only-one'] });
		expect(() => evaluateInteraction(c, { blanks: ['CO2', 'water'] })).toThrow(
			InteractionConfigError
		);
	});

	it('rejects duplicate blank ids at validation time', () => {
		const errors = validateInteractionContract(
			contract('fill-blank', { answers: ['a', 'b'], blank_ids: ['same', 'same'] })
		);
		expect(errors.join('\n')).toMatch(/unique|duplicate/i);
	});
});

describe('golden: numeric', () => {
	it('scores within the declared tolerance and not outside it', () => {
		const c = contract('numeric', { value: 9.81, tolerance: 0.05 });
		expect(evaluateInteraction(c, { value: 9.8 })).toMatchObject({ outcome: 'correct' });
		expect(evaluateInteraction(c, { value: 9.2 })).toMatchObject({ outcome: 'incorrect' });
	});

	it('rejects a non-finite target value', () => {
		for (const value of [Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY]) {
			expect(() => evaluateInteraction(contract('numeric', { value }), { value: 1 })).toThrow(
				InteractionConfigError
			);
		}
	});

	it('rejects a negative or non-finite tolerance', () => {
		for (const tolerance of [-1, Number.NaN, Number.POSITIVE_INFINITY]) {
			expect(() =>
				evaluateInteraction(contract('numeric', { value: 1, tolerance }), { value: 1 })
			).toThrow(InteractionConfigError);
		}
	});

	it('rejects a non-finite or non-numeric response', () => {
		const c = contract('numeric', { value: 1 });
		for (const value of [Number.NaN, Number.POSITIVE_INFINITY, '1' as unknown as number]) {
			expect(() => evaluateInteraction(c, { value })).toThrow(InteractionResponseError);
		}
	});

	it('reports the same failures through validation, not only at evaluation', () => {
		expect(
			validateInteractionContract(contract('numeric', { value: Number.NaN })).join('\n')
		).toMatch(/finite/i);
		expect(
			validateInteractionContract(contract('numeric', { value: 1, tolerance: -0.5 })).join('\n')
		).toMatch(/negative/i);
	});
});

describe('golden: short-response', () => {
	it('scores against declared accepted answers, normalised', () => {
		const c = contract('short-response', {
			evaluation: 'accepted-answers',
			accepted_answers: ['CO2', 'carbon dioxide']
		});
		expect(evaluateInteraction(c, { text: ' Carbon  Dioxide ' })).toMatchObject({
			outcome: 'correct',
			score_earned: 1
		});
		expect(evaluateInteraction(c, { text: 'oxygen' })).toMatchObject({ outcome: 'incorrect' });
	});

	it('is not the numeric evaluator: a numeric config is an authoring error', () => {
		const c = contract('short-response', { value: 42, tolerance: 0 });
		expect(() => evaluateInteraction(c, { text: '42' })).toThrow(InteractionConfigError);
		expect(validateInteractionContract(c).join('\n')).toMatch(/accepted-answers|teacher-review/);
	});

	it('returns pending-review with no earned score under teacher-review', () => {
		const c = contract(
			'short-response',
			{ evaluation: 'teacher-review', review_guidance: 'Look for a stated mechanism.' },
			{ completion: { type: 'submitted' } }
		);
		expect(evaluateInteraction(c, { text: 'Light energy drives glucose synthesis.' })).toMatchObject(
			{ outcome: 'pending-review', score_earned: 0, score_possible: 1 }
		);
	});

	it('rejects accepted-answers mode with no accepted answers', () => {
		const c = contract('short-response', {
			evaluation: 'accepted-answers',
			accepted_answers: []
		});
		expect(() => evaluateInteraction(c, { text: 'anything' })).toThrow(InteractionConfigError);
	});

	it('rejects an empty response rather than scoring it incorrect', () => {
		const c = contract('short-response', {
			evaluation: 'accepted-answers',
			accepted_answers: ['CO2']
		});
		expect(() => evaluateInteraction(c, { text: '   ' })).toThrow(InteractionResponseError);
	});

	it('rejects teacher-review paired with completion on correctness', () => {
		const errors = validateInteractionContract(
			contract('short-response', { evaluation: 'teacher-review' }, {
				completion: { type: 'correct' }
			})
		);
		expect(errors.join('\n')).toMatch(/teacher-review/i);
	});
});

describe('golden: match-pairs and classify', () => {
	const pairs = [
		{ left: 'chloroplast', right: 'captures light' },
		{ left: 'stomata', right: 'exchanges gas' },
		{ left: 'root-hair', right: 'absorbs water' }
	];

	it('awards one point per correct link', () => {
		const c = contract('match-pairs', { pairs });
		expect(
			evaluateInteraction(c, {
				matches: [
					{ left: 'chloroplast', right: 'captures light' },
					{ left: 'stomata', right: 'absorbs water' }
				]
			})
		).toMatchObject({ outcome: 'partial', score_earned: 1, score_possible: 3 });
	});

	it('rejects the same source submitted twice', () => {
		const c = contract('match-pairs', { pairs });
		expect(() =>
			evaluateInteraction(c, {
				matches: [
					{ left: 'stomata', right: 'exchanges gas' },
					{ left: 'stomata', right: 'absorbs water' }
				]
			})
		).toThrow(InteractionResponseError);
	});

	it('rejects a link naming an undeclared source or target', () => {
		const c = contract('match-pairs', { pairs });
		expect(() =>
			evaluateInteraction(c, { matches: [{ left: 'nucleus', right: 'captures light' }] })
		).toThrow(InteractionResponseError);
		expect(() =>
			evaluateInteraction(c, { matches: [{ left: 'stomata', right: 'makes protein' }] })
		).toThrow(InteractionResponseError);
	});

	it('rejects duplicate source ids in the config', () => {
		const c = contract('match-pairs', {
			pairs: [
				{ left: 'same', right: 'one' },
				{ left: 'same', right: 'two' }
			]
		});
		expect(() =>
			evaluateInteraction(c, { matches: [{ left: 'same', right: 'one' }] })
		).toThrow(InteractionConfigError);
	});

	it('classify evaluates single-category membership exactly as the catalogue declares', () => {
		const record = capabilityById('classify');
		expect(record?.default_behaviour.categories_per_item).toBe(1);

		const c = contract('classify', {
			categories: [
				{ id: 'reactant', label: 'Reactant' },
				{ id: 'product', label: 'Product' }
			],
			pairs: [
				{ left: 'co2', right: 'reactant' },
				{ left: 'glucose', right: 'product' }
			]
		});
		expect(
			evaluateInteraction(c, {
				matches: [
					{ left: 'co2', right: 'reactant' },
					{ left: 'glucose', right: 'product' }
				]
			})
		).toMatchObject({ outcome: 'correct', score_earned: 2, score_possible: 2 });

		// A second category for the same item is a duplicate source, so it is
		// rejected rather than silently scored — which is what makes the
		// "single category only" declaration true rather than aspirational.
		expect(() =>
			evaluateInteraction(c, {
				matches: [
					{ left: 'co2', right: 'reactant' },
					{ left: 'co2', right: 'product' }
				]
			})
		).toThrow(InteractionResponseError);
	});
});

describe('golden: sequence', () => {
	const config = { order: ['absorb', 'split', 'fix'] };

	it('awards one point per item in its expected position', () => {
		const c = contract('sequence', config);
		expect(evaluateInteraction(c, { order: ['absorb', 'split', 'fix'] })).toMatchObject({
			outcome: 'correct',
			score_earned: 3,
			score_possible: 3
		});
		expect(evaluateInteraction(c, { order: ['absorb', 'fix', 'split'] })).toMatchObject({
			outcome: 'partial',
			score_earned: 1,
			score_possible: 3
		});
	});

	it('rejects a duplicate, short or unknown ordering', () => {
		const c = contract('sequence', config);
		expect(() => evaluateInteraction(c, { order: ['absorb', 'absorb', 'fix'] })).toThrow(
			InteractionResponseError
		);
		expect(() => evaluateInteraction(c, { order: ['absorb', 'split'] })).toThrow(
			InteractionResponseError
		);
		expect(() => evaluateInteraction(c, { order: ['absorb', 'split', 'zzz'] })).toThrow(
			InteractionResponseError
		);
	});

	it('rejects duplicate item ids in the config', () => {
		const c = contract('sequence', { order: ['a', 'a', 'b'] });
		expect(() => evaluateInteraction(c, { order: ['a', 'a', 'b'] })).toThrow(
			InteractionConfigError
		);
	});
});

describe('golden: attempt limits', () => {
	it('stops accepting attempts at the declared maximum', () => {
		const c = contract('choice', CHOICE_CONFIG);
		expect(c.attempt_policy.max_attempts).toBe(2);

		let state = createAttemptState(c.id);
		state = recordAttempt(state, c, { selected_option_id: 'a' });
		state = recordAttempt(state, c, { selected_option_id: 'c' });
		expect(state.attempt_count).toBe(2);
		expect(state.completed).toBe(false);

		// A third attempt against a two-attempt policy must not be scored: the
		// state comes back untouched, so a correct late answer cannot be recorded.
		const refused = recordAttempt(state, c, { selected_option_id: 'b' });
		expect(refused).toBe(state);
		expect(refused.attempt_count).toBe(2);
		expect(refused.last_result?.outcome).toBe('incorrect');
		expect(refused.responses).toHaveLength(2);
	});

	it('refuses a retry after a correct answer when the policy forbids it', () => {
		const c = contract('choice', CHOICE_CONFIG);
		expect(c.attempt_policy.allow_retry_after_correct).toBe(false);
		const state = recordAttempt(createAttemptState(c.id), c, { selected_option_id: 'b' });
		expect(recordAttempt(state, c, { selected_option_id: 'a' })).toBe(state);
	});

	it('marks the interaction complete as soon as the completion rule is met', () => {
		const c = contract('choice', CHOICE_CONFIG);
		const state = recordAttempt(createAttemptState(c.id), c, { selected_option_id: 'b' });
		expect(state.completed).toBe(true);
		expect(state.last_result?.outcome).toBe('correct');
	});

	it('allows unlimited practice attempts where the policy says so', () => {
		const c = contract('fill-blank', { answers: ['water'] }, {
			assessment_mode: 'practice',
			attempt_policy: {
				max_attempts: null,
				show_feedback_after_submit: true,
				allow_retry_after_correct: true
			},
			completion: { type: 'submitted' }
		});
		let state = createAttemptState(c.id);
		for (let i = 0; i < 5; i += 1) {
			state = recordAttempt(state, c, { blanks: ['soil'] });
		}
		expect(state.attempt_count).toBe(5);
	});
});

describe('golden coverage', () => {
	/**
	 * Every auto-scored capability must have a golden case. Without this, adding
	 * a kind silently adds an untested evaluator.
	 */
	it('covers every auto-scored capability that declares partial scoring honestly', () => {
		const autoScored = learnCapabilities.filter(
			(record) => record.kind === 'interaction' && record.evaluation.mode === 'auto-score'
		);
		expect(autoScored.map((record) => record.id).sort()).toEqual([
			'choice',
			'classify',
			'drag-label',
			'fill-blank',
			'image-hotspot',
			'match-pairs',
			'multi-select',
			'numeric',
			'sequence',
			'short-response'
		]);

		// Partial scoring is a claim about the evaluator, so it must match the
		// evaluator the record actually names.
		const partialByEvaluator: Record<string, boolean> = {
			evaluateChoice: false,
			evaluateNumeric: false,
			evaluateShortResponse: false,
			evaluateMultiSelect: true,
			evaluateFillBlank: true,
			evaluateMatchPairs: true,
			evaluateSequence: true
		};
		for (const record of autoScored) {
			const evaluator = record.evaluation.contract_ref?.split('#')[1] ?? '';
			expect(
				record.evaluation.partial_scoring,
				`${record.id} claims partial_scoring=${record.evaluation.partial_scoring} but uses ${evaluator}`
			).toBe(partialByEvaluator[evaluator]);
		}
	});
});
