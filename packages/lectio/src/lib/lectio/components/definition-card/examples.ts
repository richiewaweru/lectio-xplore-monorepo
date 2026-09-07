import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		"term": "Term",
		"formal": "Formal def.",
		"plain": "Plain def."
	}
];
