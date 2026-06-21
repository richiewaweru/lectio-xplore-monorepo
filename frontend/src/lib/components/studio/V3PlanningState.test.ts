import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import V3PlanningState from './V3PlanningState.svelte';

describe('V3PlanningState', () => {
	it('renders teacher inputs when form is present', () => {
		render(V3PlanningState, {
			props: {
				form: {
					grade_level: 'Grade 7',
					subject: 'Mathematics',
					duration_minutes: 50,
					resource_type: 'lesson',
					topic: 'Compound area',
					subtopics: ['L-shapes'],
					prior_knowledge: '',
					outcome: 'Students can find the area of compound shapes.',
					struggle: 'They may forget to split the shape into rectangles.',
					learner_level: 'on_grade',
					reading_level: 'on_grade',
					language_support: 'some_ell',
					prior_knowledge_level: 'new_topic',
					free_text: ''
				},
				signals: {
					topic: 'Compound area',
					subtopic: 'L-shapes',
					prior_knowledge: [],
					learner_needs: [],
					teacher_goal: 'Students can find the area of compound shapes.',
					inferred_lesson_mode: 'first_exposure',
					lesson_mode_confidence: 'high'
				}
			}
		});

		expect(screen.getByText('Grade')).toBeTruthy();
		expect(screen.getByText('Grade 7')).toBeTruthy();
		expect(screen.getByText('Compound area')).toBeTruthy();
		expect(screen.getByText(/First exposure mode/i)).toBeTruthy();
	});
});

