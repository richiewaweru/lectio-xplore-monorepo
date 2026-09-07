import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		"title": "Compare",
		"columns": [
			{
				"id": "c1",
				"title": "A",
				"summary": "SA"
			}
		],
		"rows": [
			{
				"criterion": "Speed",
				"values": [
					"Fast"
				],
				"takeaway": ""
			}
		]
	}
];
