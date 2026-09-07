import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		"items": [
			{
				"text": "Idea one"
			},
			{
				"text": "Idea two"
			}
		]
	}
];
