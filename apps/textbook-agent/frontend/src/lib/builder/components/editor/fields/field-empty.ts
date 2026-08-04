import type { FieldSchema } from 'lectio';

/** Default empty value for one row of an object-list from `itemSchema`. */
export function emptyObjectFromItemSchema(fields: FieldSchema[]): Record<string, unknown> {
	const obj: Record<string, unknown> = {};
	for (const f of fields) {
		if (f.input === 'list' || f.input === 'object-list') {
			obj[f.field] = [];
		} else if (f.input === 'boolean') {
			obj[f.field] = false;
		} else if (f.input === 'number') {
			obj[f.field] = 0;
		} else if (f.input === 'hidden') {
			continue;
		} else {
			obj[f.field] = '';
		}
	}
	return obj;
}
