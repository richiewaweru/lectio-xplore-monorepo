import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		"problems": [
			{
				"difficulty": "warm",
				"question": "Try this.",
				"hints": [
					{
						"level": 1,
						"text": "Hint one"
					}
				]
			},
			{
				"difficulty": "medium",
				"question": "Try that.",
				"hints": [
					{
						"level": 1,
						"text": "Hint one"
					}
				]
			}
		]
	}
];
