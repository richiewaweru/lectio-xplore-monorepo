import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		"title": "Intro",
		"subject": "Mathematics",
		"grade_band": "secondary"
	}
];
