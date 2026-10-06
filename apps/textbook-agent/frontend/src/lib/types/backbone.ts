/** Lesson backbone: the shared scenario, data, and figure specs for a preparation. */

export interface BackboneAnchor {
	id: string;
	story: string;
	data: Record<string, unknown>;
	answer: string | null;
	figure_ids: string[];
}

export interface BackboneVariant {
	id: string;
	change: string;
	data: Record<string, unknown>;
	answer: string | null;
	figure_ids: string[];
}

export interface BackboneFigure {
	id: string;
	purpose: string;
	must_show: string[];
	labels_required: string[];
	data: Record<string, unknown>;
}

export interface LessonBackbone {
	anchor: BackboneAnchor;
	variants: BackboneVariant[];
	figures: BackboneFigure[];
}

/** Response of GET /api/v1/preparations/{id}/backbone. */
export interface PreparationBackbone {
	backbone: LessonBackbone;
	hash: string;
}
