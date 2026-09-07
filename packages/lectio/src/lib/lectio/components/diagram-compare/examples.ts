import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		"before_label": "Before",
		"after_label": "After",
		"caption": "Compare both states.",
		"alt_text": "Side-by-side diagram comparison."
	}
];
