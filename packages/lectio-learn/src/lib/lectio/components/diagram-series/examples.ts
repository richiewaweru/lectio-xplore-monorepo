import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		"title": "Steps",
		"diagrams": [
			{
				"step_label": "1",
				"caption": "First frame.",
				"svg_content": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"1\" height=\"1\"/>"
			}
		]
	}
];
