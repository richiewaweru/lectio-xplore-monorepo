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

	/** JSON pointer into `lectio-document-v2.schema.json` for the exact payload. */
	payload_schema_ref?: string;

	/** Canonical learner actions this form can satisfy on paper. Empty for chrome. */
	supported_actions?: string[];

	/** Why the action list stops where it does, when that needs saying. */
	supported_actions_note?: string;

	/** False for document chrome and derived teacher content a selector never picks. */
	form_selectable?: boolean;

	/** Required when `form_selectable` is false. */
	not_form_selectable_because?: string;

	/** Per-field authoring guidance. One entry per `content_schema` field. */
	writer_guidance?: Record<string, string>;

	/** Authoring shapes that must be rejected. Guidance, not executable validation. */
	negative_cases?: string[];

	/** True when the form cannot render without a resolved asset reference. */
	requires_asset?: boolean;

	/** Asset kinds and identity rules for asset-bearing forms. */
	asset_requirements?: { kinds: string[]; identity: string };

	/** True when the teacher edition derives answer-key entries from this form. */
	produces_answer_key?: boolean;

	/** True for content that must never reach the student edition. */
	teacher_edition_only?: boolean;
}

const objects = objectCatalogue.objects as Record<string, ObjectRecord>;

export function getObject(id: PageObject): ObjectRecord | undefined {
	return objects[id];
}

export function listObjects(): PageObject[] {
	return Object.keys(objects) as PageObject[];
}

export { objects as objectRecords };
