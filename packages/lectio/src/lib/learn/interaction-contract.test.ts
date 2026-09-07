import { describe, expect, it } from 'vitest';
import {
	completeLessonInMemory,
	createAttemptState,
	evaluateInteraction,
	fillBlankContentToInteractionContract,
	parseInteractionContract,
	quizContentToInteractionContract,
	recordAttempt,
	serializeInteractionContract,
	validateInteractionContract,
	type LearnInteractionContract
} from './interaction-contract';

describe('Learn interaction contracts', () => {
	it('evaluates choice correct/incorrect deterministically', () => {
		const contract = quizContentToInteractionContract({
			question: 'Where does plant mass come from?',
			options: [
				{ text: 'Soil', correct: false },
				{ text: 'Air (CO2)', correct: true },
				{ text: 'Sunlight alone', correct: false }
			],
			feedback_correct: 'Yes — carbon from CO2.',
			feedback_incorrect: 'Not quite.'
		});
		expect(validateInteractionContract(contract)).toEqual([]);
		const ok = evaluateInteraction(contract, { selected_option_id: '1' });
		expect(ok.outcome).toBe('correct');
		expect(ok.score_earned).toBe(1);
		const bad = evaluateInteraction(contract, { selected_option_id: '0' });
		expect(bad.outcome).toBe('incorrect');
	});

	it('evaluates multi-select partial credit', () => {
		const contract: LearnInteractionContract = {
			id: 'ms1',
			kind: 'multi-select',
			prompt: 'Select reactants',
			assessment_mode: 'graded',
			attempt_policy: {
				max_attempts: 3,
				show_feedback_after_submit: true,
				allow_retry_after_correct: false
			},
			feedback: { correct: 'All good', incorrect: 'Missed some', partial: 'Partial' },
			completion: { type: 'score_at_least', min_ratio: 0.5 },
			config: { correct_option_ids: ['a', 'b'] },
			accessibility: { keyboard_operable: true },
			ai_config_rule: 'config-only'
		};
		const partial = evaluateInteraction(contract, { selected_option_ids: ['a'] });
		expect(partial.outcome).toBe('partial');
		expect(partial.score_earned).toBe(1);
	});

	it('evaluates fill-blank via upgraded content adapter', () => {
		const contract = fillBlankContentToInteractionContract({
			instruction: 'Complete',
			segments: [
				{ text: 'Plants take in ', is_blank: false },
				{ text: '', is_blank: true, answer: 'CO2' },
				{ text: ' and water.', is_blank: false }
			]
		});
		expect(evaluateInteraction(contract, { blanks: ['co2'] }).outcome).toBe('correct');
		expect(evaluateInteraction(contract, { blanks: ['soil'] }).outcome).toBe('incorrect');
	});

	it('serializes and validates strictly', () => {
		const contract = quizContentToInteractionContract({
			question: 'Q',
			options: [
				{ text: 'A', correct: true },
				{ text: 'B', correct: false }
			],
			feedback_correct: 'ok',
			feedback_incorrect: 'no'
		});
		const raw = serializeInteractionContract(contract);
		const parsed = parseInteractionContract(raw);
		expect(parsed.id).toBe(contract.id);
		expect(() =>
			parseInteractionContract(
				JSON.stringify({ ...contract, ai_config_rule: 'execute-code' })
			)
		).toThrow(/config-only/);
	});

	it('records attempts and completes an in-memory fixture lesson', () => {
		const quiz = quizContentToInteractionContract({
			question: 'Q',
			options: [
				{ text: 'A', correct: true },
				{ text: 'B', correct: false }
			],
			feedback_correct: 'ok',
			feedback_incorrect: 'no'
		});
		const numeric: LearnInteractionContract = {
			id: 'num1',
			kind: 'numeric',
			prompt: '6 * 7',
			assessment_mode: 'graded',
			attempt_policy: {
				max_attempts: 2,
				show_feedback_after_submit: true,
				allow_retry_after_correct: false
			},
			feedback: { correct: '42', incorrect: 'retry' },
			completion: { type: 'correct' },
			config: { value: 42, tolerance: 0 },
			accessibility: { keyboard_operable: true, narration: 'optional' },
			ai_config_rule: 'config-only'
		};
		const sequence: LearnInteractionContract = {
			id: 'seq1',
			kind: 'sequence',
			prompt: 'Order the steps',
			assessment_mode: 'practice',
			attempt_policy: {
				max_attempts: null,
				show_feedback_after_submit: true,
				allow_retry_after_correct: true
			},
			feedback: { correct: 'ordered', incorrect: 'reorder', partial: 'close' },
			completion: { type: 'submitted' },
			config: { order: ['1', '2', '3'] },
			accessibility: { keyboard_operable: true },
			ai_config_rule: 'config-only'
		};

		let state = recordAttempt(createAttemptState(quiz.id), quiz, { selected_option_id: '0' });
		expect(state.completed).toBe(true);

		const result = completeLessonInMemory([quiz, numeric, sequence], {
			[quiz.id]: { selected_option_id: '0' },
			num1: { value: 42 },
			seq1: { order: ['1', '2', '3'] }
		});
		expect(result.completed).toBe(true);
		expect(result.score_earned).toBeGreaterThan(0);
		expect(result.score_possible).toBeGreaterThan(0);
	});
});
