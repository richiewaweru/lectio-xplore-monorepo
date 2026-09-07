import type { z } from 'zod';
import { componentSchema } from './schema';

type ExampleDatum = z.infer<typeof componentSchema>;

export const examples: ExampleDatum[] = [
	{
		"spec": {
			"type": "sandbox",
			"goal": "Explore the slider effect on the graph.",
			"anchor_content": {},
			"context": {
				"learner_level": "secondary",
				"template_id": "sandbox",
				"color_mode": "light",
				"accent_color": "#0f172a",
				"surface_color": "#ffffff",
				"font_mono": "ui-monospace"
			},
			"dimensions": {
				"width": "100%",
				"height": 420,
				"resizable": true
			},
			"print_translation": "static_diagram"
		}
	}
];
