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
		responseEvaluation: 'self-check',
		narration: 'optional',
		learnerBand: 'core',
		accessibilityNotes: 'Provide keyboard-accessible hint reveal and solution toggle.'
	},
	examples,
	contentContract
} satisfies LectioContentModule;
