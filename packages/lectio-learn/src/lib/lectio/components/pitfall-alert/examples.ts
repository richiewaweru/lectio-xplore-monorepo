import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		misconception: 'Wrong idea',
		correction: 'Right idea.'
	},
	{
		label: 'Exam Trap',
		misconception: 'Heavier objects fall faster',
		correction: 'In a vacuum, all objects accelerate at the same rate regardless of mass.'
	}
];
