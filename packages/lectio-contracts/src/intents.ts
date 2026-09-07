import intentVocabulary from '../data/instructional-intents.v1.json';

/**
 * Canonical instructional intent identifier.
 *
 * The identifiers are owned by the Print intent catalogue
 * (`@lectio/page` `contracts/intent-catalogue.v1.json`) and copied here without
 * renaming so both native paths speak one vocabulary. New identifiers are added
 * upstream first; `scripts/export-contracts.ts` re-syncs this file.
 */
export type InstructionalIntentId = keyof typeof intentVocabulary.intents;

export interface InstructionalIntentRecord {
	/** Teacher-facing label. */
	label: string;
	/** What the intent does for the lesson. */
	pedagogical_role: string;
	/** The cognitive work the learner performs. */
	cognitive_job: string;
	/** Testable condition for choosing this intent, when the source declares one. */
	choose_when: string | null;
	/** Neighbouring intents that are the better fit, keyed by intent id. */
	boundaries: Partial<Record<string, string>>;
	/**
	 * False when the intent is never chosen during teaching planning because the
	 * native path derives it (for example teacher answer guidance).
	 */
	teaching_selectable: boolean;
}

const intents = intentVocabulary.intents as unknown as Record<string, InstructionalIntentRecord>;

export const INSTRUCTIONAL_VOCABULARY_VERSION = intentVocabulary.vocabulary_version;

export const INSTRUCTIONAL_INTENT_SOURCE = intentVocabulary.source;

/** Every canonical intent id, including intents the teaching layer never selects. */
export const INSTRUCTIONAL_INTENT_IDS = Object.keys(intents) as InstructionalIntentId[];

export function getInstructionalIntent(id: string): InstructionalIntentRecord | undefined {
	return intents[id];
}

export function isInstructionalIntentId(id: string): id is InstructionalIntentId {
	return Object.hasOwn(intents, id);
}

export function isTeachingSelectableIntent(id: string): boolean {
	return intents[id]?.teaching_selectable === true;
}

/** Intents a shared teaching plan is allowed to choose. */
export function listTeachingSelectableIntentIds(): InstructionalIntentId[] {
	return INSTRUCTIONAL_INTENT_IDS.filter((id) => isTeachingSelectableIntent(id));
}

/** Neighbouring-intent boundaries as an ordered list rather than a keyed object. */
export function listIntentBoundaries(id: string): Array<{ intent: string; when: string }> {
	const record = intents[id];
	if (!record) return [];
	return Object.entries(record.boundaries)
		.filter((entry): entry is [string, string] => typeof entry[1] === 'string')
		.map(([intent, when]) => ({ intent, when }));
}

export { intents as instructionalIntentRecords };
