import type { IntentId, PageObject } from '../contract/intents';
import intentCatalogue from '../../../contracts/intent-catalogue.v1.json';

export interface IntentRecord {
	teacher_label: string;
	pedagogical_role: string;
	cognitive_job: string;
	valid_objects: PageObject[];
	generation_guidance: string;

	/** Testable condition for choosing this intent. Optional during v1.1 rollout. */
	choose_when?: string;

	/** Cluster-mate boundaries: when a neighbouring intent is the better fit. */
	not_when?: Partial<Record<IntentId, string>>;

	/** False when the intent is never chosen by the selector. Defaults to true. */
	selectable?: boolean;
}

const intents = intentCatalogue.intents as Record<string, IntentRecord>;

export function getIntent(id: IntentId): IntentRecord | undefined {
	return intents[id];
}

export function listIntents(): IntentId[] {
	return Object.keys(intents) as IntentId[];
}

export function isCompatible(object: PageObject, intent: IntentId): boolean {
	if (object === 'heading') return false;
	const record = intents[intent];
	if (!record) return false;
	return record.valid_objects.includes(object);
}

export function isSelectable(id: IntentId): boolean {
	return intents[id]?.selectable !== false;
}

export function listSelectableIntents(): IntentId[] {
	return listIntents().filter(isSelectable);
}

export { intents as intentRecords };
