import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		headline: 'Why?',
		body: 'Because.',
		anchor: 'Need'
	},
	{
		headline: 'What happens when the lights go out?',
		body: 'A forest at night reveals a hidden world of chemical reactions that only begin after sunset.',
		anchor: 'photosynthesis stops and respiration dominates',
		image: {
			url: 'https://placehold.co/800x400/e2e8f0/334155?text=Forest+at+dusk',
			alt: 'Forest silhouette at dusk'
		}
	}
];
