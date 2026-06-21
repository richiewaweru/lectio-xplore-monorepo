import type {
	BlueprintPreviewDTO,
	CanvasSection,
	ComponentStatus,
	V3StructuralPlan
} from '$lib/types/v3';

export function buildCanvasSkeleton(blueprint: BlueprintPreviewDTO): CanvasSection[] {
	const sorted = [...blueprint.section_plan].sort((a, b) => a.order - b.order);
	return sorted.map((section) => ({
		id: section.id,
		title: section.title,
		teacher_labels: section.components.map((c) => c.teacher_label).join(' · '),
		order: section.order,
		components: section.components.map((c) => ({
			id: c.component_id,
			teacher_label: c.teacher_label,
			status: 'pending' as ComponentStatus,
			data: null
		})),
		visual: section.visual_required
			? {
					id: `visual-${section.id}`,
					status: 'pending' as ComponentStatus,
					image_url: null,
					frame_index: null
				}
			: null,
		questions: blueprint.question_plan
			.filter((q) => q.attaches_to_section_id === section.id)
			.map((q) => ({
				id: q.id,
				difficulty: q.difficulty,
				status: 'pending' as ComponentStatus,
				data: null
			})),
		mergedFields: {}
	}));
}

export function buildStructuralPlanCanvas(plan: V3StructuralPlan): CanvasSection[] {
	return plan.sections.map((section, index) => ({
		id: section.id,
		title: section.title,
		teacher_labels: section.components.map((component) => component.slug).join(' · '),
		order: index,
		components: section.components.map((component) => ({
			id: component.slug,
			teacher_label: component.slug,
			status: 'pending' as ComponentStatus,
			data: null
		})),
		visual: section.visual_required
			? {
					id: `visual-${section.id}`,
					status: 'pending' as ComponentStatus,
					image_url: null,
					frame_index: null
				}
			: null,
		questions: plan.question_plan
			.filter((question) => question.section_id === section.id)
			.map((question) => ({
				id: question.question_id,
				difficulty: question.temperature,
				status: 'pending' as ComponentStatus,
				data: null
			})),
		mergedFields: {}
	}));
}

export function patchCanvasSection(
	sections: CanvasSection[],
	sectionId: string,
	patch: (section: CanvasSection) => CanvasSection
): CanvasSection[] {
	return sections.map((s) => (s.id === sectionId ? patch(s) : s));
}

/** Merge component block into Lectio-shaped section fields */
export function mergeComponentField(
	merged: Record<string, unknown>,
	sectionField: string,
	data: Record<string, unknown>
): Record<string, unknown> {
	return { ...merged, [sectionField]: data };
}

export function mergeDiagramFrame(
	merged: Record<string, unknown>,
	payload: { image_url?: string | null; frame_index?: number | null }
): Record<string, unknown> {
	const url = payload.image_url ?? '';
	const fi = payload.frame_index;
	const next = { ...merged };
	if (fi == null) {
		next.diagram = { image_url: url, caption: '', alt_text: '' };
		return next;
	}
	const ds = (next.diagram_series as Record<string, unknown> | undefined) ?? {
		title: '',
		diagrams: [] as unknown[]
	};
	const diagrams = [...((ds.diagrams as unknown[]) ?? [])];
	while (diagrams.length <= fi) {
		diagrams.push({
			step_label: `Frame ${diagrams.length + 1}`,
			caption: '',
			image_url: ''
		});
	}
	const step = diagrams[fi] as Record<string, unknown>;
	diagrams[fi] = {
		...step,
		image_url: url,
		caption: step.caption ?? `Frame ${fi + 1}`
	};
	next.diagram_series = { ...ds, diagrams };
	return next;
}

export function mergePracticeProblem(
	merged: Record<string, unknown>,
	questionId: string,
	difficulty: string,
	data: Record<string, unknown>
): Record<string, unknown> {
	const next = { ...merged };
	const practice = (next.practice as Record<string, unknown> | undefined) ?? {};
	const problems = [...((practice.problems as unknown[]) ?? [])] as Record<string, unknown>[];
	const stem =
		(typeof data.question === 'string' && data.question) ||
		(typeof data.stem === 'string' && data.stem) ||
		'';
	const idx = problems.findIndex((p) => (p as { _qid?: string })._qid === questionId);
	const row: Record<string, unknown> = {
		_qid: questionId,
		difficulty,
		question: stem,
		hints: Array.isArray(data.hints) ? data.hints : [],
		problem_type: typeof data.problem_type === 'string' ? data.problem_type : 'open'
	};
	if (typeof data.diagram === 'object' && data.diagram) row.diagram = data.diagram;
	if (idx >= 0) problems[idx] = row;
	else problems.push(row);
	next.practice = {
		...practice,
		problems,
		label: (practice.label as string) ?? 'Practice Questions',
		hints_visible_default: practice.hints_visible_default ?? false,
		solutions_available: practice.solutions_available ?? true
	};
	return next;
}
