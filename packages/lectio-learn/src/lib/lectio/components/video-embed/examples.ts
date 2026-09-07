import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		"media_id": "demo-media",
		"print_fallback": "thumbnail"
	}
];
