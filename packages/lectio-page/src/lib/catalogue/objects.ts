import objectCatalogue from '../../../contracts/object-catalogue.v1.json';
import type { PageObject } from '../contract/intents';

export type CapacityLimits = Record<string, number>;

export interface ObjectRecord {
	holds: string;
	content_schema: Record<string, string>;
	placement: string[];
	fragmentation: string;
	emphasis: string;
	screen_layer: string;

	/** Positive test: what must be true of the brief for this object to beat prose. */
	earns_its_place_when?: string;

	/** Counter-test. Makes the choice binary rather than a judgement call. */
	reject_when?: string;

	/** Print-derived limits. Flat numeric keys; Min/Max suffixes for ranges. */
	capacity?: CapacityLimits;
}

const objects = objectCatalogue.objects as Record<string, ObjectRecord>;

export function getObject(id: PageObject): ObjectRecord | undefined {
	return objects[id];
}

export function listObjects(): PageObject[] {
	return Object.keys(objects) as PageObject[];
}

export { objects as objectRecords };
