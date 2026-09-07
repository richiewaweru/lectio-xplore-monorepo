import type { SectionContent } from '$lib/schema/types';

import { lectioComponentModules } from './components';

/** Component id → `SectionContent` field; omits `sectionField: null`. */
export function getComponentFieldMap(): Record<string, keyof SectionContent> {
	const map: Record<string, keyof SectionContent> = {};
	for (const component of lectioComponentModules) {
		const field = component.metadata.sectionField;
		if (field !== null && field !== undefined) {
			map[component.metadata.id] = field as keyof SectionContent;
		}
	}
	return map;
}
