import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		"body": "Next unit builds on this.",
		"next": "Quadratics",
		"preview": "Preview."
	}
];
