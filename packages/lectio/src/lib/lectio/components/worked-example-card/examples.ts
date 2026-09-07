import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		"title": "Demo",
		"setup": "Problem setup.",
		"steps": [
			{
				"label": "Step 1",
				"content": "Do this."
			}
		],
		"conclusion": "Done."
	}
];
