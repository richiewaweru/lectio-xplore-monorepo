import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		"segments": [
			{
				"text": "The answer is ",
				"is_blank": false
			},
			{
				"text": "",
				"is_blank": true,
				"answer": "x"
			}
		]
	}
];
