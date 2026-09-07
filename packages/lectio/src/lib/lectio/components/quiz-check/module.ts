import { componentSchema } from './schema';
import { metadata } from './metadata';
import { print } from './print';
import { examples } from './examples';
import { contentContract } from './content-contract';
import type { LectioContentModule } from '$lib/lectio/core/types';

export const lectioModule = {
	schema: componentSchema,
	metadata,
	print,
	web: {
		interaction: 'choice',
		responseEvaluation: 'auto-score',
		narration: 'optional',
		learnerBand: 'core',
		accessibilityNotes: 'Expose option labels to assistive tech; announce correctness feedback.'
	},
	examples,
	contentContract
} satisfies LectioContentModule;
