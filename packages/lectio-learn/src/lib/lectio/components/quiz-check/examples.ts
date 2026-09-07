import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		"question": "Pick one.",
		"options": [
			{
				"text": "A",
				"correct": false,
				"explanation": "No."
			},
			{
				"text": "B",
				"correct": true,
				"explanation": "Yes."
			},
			{
				"text": "C",
				"correct": false,
				"explanation": "No."
			}
		],
		"feedback_correct": "Nice.",
		"feedback_incorrect": "Review."
	}
];
