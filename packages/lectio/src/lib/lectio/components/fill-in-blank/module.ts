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
		interaction: 'input',
		responseEvaluation: 'auto-score',
		narration: 'optional',
		learnerBand: 'support',
		accessibilityNotes: 'Blanks must be reachable by keyboard; word bank items labeled.'
	},
	examples,
	contentContract
} satisfies LectioContentModule;
