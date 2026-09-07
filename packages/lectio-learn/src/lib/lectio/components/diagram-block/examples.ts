import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		caption: 'A labelled diagram for the lesson.',
		alt_text: 'Diagram showing key parts referenced in the prose.'
	},
	{
		caption: 'Position–time graph for uniform acceleration.',
		alt_text: 'Curved line on axes labelled time and position.',
		figure_ref: 'Figure 2.1',
		description:
			'The curve bends upward because velocity increases over time. Notice how equal time steps cover larger distances — that is the signature of acceleration.',
		svg_content:
			'<svg viewBox="0 0 200 120" xmlns="http://www.w3.org/2000/svg"><path d="M20 100 Q100 20 180 40" fill="none" stroke="#333" stroke-width="2"/></svg>'
	}
];
