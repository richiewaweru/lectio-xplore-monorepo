import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		"cells": [
			{
				"label": "A",
				"value": "1"
			},
			{
				"label": "B",
				"value": "2"
			}
		]
	}
];
