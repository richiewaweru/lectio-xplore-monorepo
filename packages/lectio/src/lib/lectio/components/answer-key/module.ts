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
	examples,
	contentContract
} satisfies LectioContentModule;
