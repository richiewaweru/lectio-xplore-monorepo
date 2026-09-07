import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		"terms": [
			{
				"term": "Omega",
				"definition": "A Greek letter commonly used as a variable."
			}
		]
	}
];
