import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		label: 'Answer key',
		entries: [
			{
				question_number: 1,
				question: 'A tree gains 50 kg of wood. Where did most of that mass come from?',
				correct_key: 'a',
				correct_answer: 'carbon dioxide from the air',
				diagnostics: [
					{
						option_key: 'b',
						option_text: 'minerals from the soil',
						misconception_id: 'M1',
						misconception_label: 'mass comes from the soil'
					}
				]
			}
		]
	}
];
