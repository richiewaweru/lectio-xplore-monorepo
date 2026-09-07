import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		fact: 'E = mc²'
	},
	{
		fact: 'The Essential Equation of Photosynthesis',
		formula: '6CO_2 + 6H_2O + \\text{light energy} \\rightarrow C_6H_{12}O_6 + 6O_2',
		context: 'Carbon Dioxide + Water + Light → Glucose + Oxygen'
	}
];
