import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		"title": "Timeline",
		"events": [
			{
				"id": "e1",
				"year": "1066",
				"title": "Event",
				"summary": "What happened."
			}
		]
	}
];
