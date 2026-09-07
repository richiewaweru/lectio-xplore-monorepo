import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		"media_id": "img-1",
		"alt_text": "Alt text describing the instructional image.",
		"caption": "Figure 1."
	}
];
