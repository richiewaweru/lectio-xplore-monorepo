import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		"family_title": "Related",
		"definitions": [
			{
				"term": "A",
				"formal": "FA",
				"plain": "PA"
			}
		]
	}
];
