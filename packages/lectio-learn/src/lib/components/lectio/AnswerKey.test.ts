import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import AnswerKey from './AnswerKey.svelte';

describe('AnswerKey', () => {
	it('renders diagnostic wording as evidence rather than a finding', () => {
		const { container } = render(AnswerKey, {
			props: {
				content: {
					entries: [
						{
							question_number: 1,
							question: 'Where did most of the tree mass come from?',
							correct_key: 'a',
							correct_answer: 'carbon dioxide from the air',
							diagnostics: [
								{
									option_key: 'b',
									option_text: 'minerals from the soil',
									misconception_id: 'M1',
									misconception_label: 'mass comes from the soil'
								}
							]
						}
					]
				}
			}
		});

		expect(screen.getByRole('region', { name: 'Answer key' })).toBeInTheDocument();
		expect(screen.getByRole('list')).toBeInTheDocument();
		expect(screen.getByText(/indicative, not conclusive/i)).toBeInTheDocument();
		expect(container.textContent?.replace(/\s+/g, ' ')).toContain(
			'chose "minerals from the soil" → consistent with: mass comes from the soil'
		);
		expect(container.textContent).not.toContain('students who hold');
	});

	it('omits diagnostics markup for an untagged entry', () => {
		const { container } = render(AnswerKey, {
			props: {
				content: {
					label: 'Teacher key',
					entries: [
						{
							question_number: 4,
							question: 'A deliberately long question that may wrap across several lines.',
							correct_answer: 'The supported answer'
						}
					]
				}
			}
		});

		expect(screen.getByRole('region', { name: 'Teacher key' })).toBeInTheDocument();
		expect(container.querySelector('.answer-key-diagnostics')).toBeNull();
	});

	it('renders the specified empty state without an entries container', () => {
		const { container } = render(AnswerKey, {
			props: { content: { entries: [] } }
		});

		expect(screen.getByText('No questions in this pack.')).toBeInTheDocument();
		expect(container.querySelector('.answer-key-entries')).toBeNull();
	});
});
