import { z } from 'zod';

const DifficultySchema = z.enum(['warm', 'medium', 'cold', 'extension']);
const GradeBandSchema = z.enum(['primary', 'secondary', 'advanced']);
const HintLevelSchema = z.union([z.literal(1), z.literal(2), z.literal(3)]);

const HookTypeSchema = z.enum(['prose', 'quote', 'question', 'data-point']);

export const SectionHeaderSchema = z
	.object({
		title: z.string(),
		subtitle: z.string().optional(),
		subject: z.string(),
		section_number: z.string().optional(),
		grade_band: GradeBandSchema,
		objectives: z.array(z.string()).optional(),
		level_pills: z
			.array(
				z.object({
					label: z.string(),
					variant: z.enum(['all', 'warm', 'medium', 'cold'])
				})
			)
			.optional()
	})
	.passthrough();

export const HookHeroSchema = z
	.object({
		headline: z.string(),
		body: z.string(),
		anchor: z.string(),
		type: HookTypeSchema.optional(),
		image: z
			.object({
				url: z.string(),
				alt: z.string()
			})
			.optional(),
		svg_content: z.string().optional(),
		quote_attribution: z.string().optional(),
		question_options: z.array(z.string()).optional(),
		data_point: z
			.object({
				value: z.string(),
				label: z.string(),
				source: z.string().optional()
			})
			.optional()
	})
	.passthrough();

export const ExplanationSchema = z
	.object({
		body: z.string(),
		emphasis: z.array(z.string()),
		callouts: z
			.array(
				z.object({
					type: z.enum([
						'remember',
						'insight',
						'sidenote',
						'warning',
						'exam-tip'
					]),
					text: z.string()
				})
			)
			.optional()
	})
	.passthrough();

export const PrerequisiteSchema = z
	.object({
		label: z.string().optional(),
		items: z.array(
			z.object({
				concept: z.string(),
				refresher: z.string().optional()
			})
		)
	})
	.passthrough();

export const WhatNextSchema = z
	.object({
		body: z.string(),
		next: z.string(),
		preview: z.string().optional(),
		prerequisites: z.array(z.string()).optional()
	})
	.passthrough();

export const InterviewSchema = z
	.object({
		prompt: z.string(),
		audience: z.string(),
		follow_up: z.string().optional()
	})
	.passthrough();

export const CalloutBlockSchema = z
	.object({
		variant: z.enum(['info', 'tip', 'warning', 'exam-tip', 'remember']),
		heading: z.string().optional(),
		body: z.string()
	})
	.passthrough();

export const SummaryBlockSchema = z
	.object({
		heading: z.string().optional(),
		items: z.array(z.object({ text: z.string() })),
		closing: z.string().optional()
	})
	.passthrough();

export const DividerSchema = z
	.object({
		label: z.string()
	})
	.passthrough();

export const DefinitionSchema = z
	.object({
		term: z.string(),
		formal: z.string(),
		plain: z.string(),
		etymology: z.string().optional(),
		notation: z.string().optional(),
		related_terms: z.array(z.string()).optional(),
		symbol: z.string().optional(),
		examples: z.array(z.string()).optional()
	})
	.passthrough();

export const DefinitionFamilySchema = z
	.object({
		family_title: z.string(),
		family_intro: z.string().optional(),
		definitions: z.array(DefinitionSchema)
	})
	.passthrough();

export const GlossarySchema = z
	.object({
		terms: z.array(
			z.object({
				term: z.string(),
				definition: z.string(),
				used_in: z.string().optional(),
				pronunciation: z.string().optional(),
				related: z.array(z.string()).optional()
			})
		)
	})
	.passthrough();

/** Inline glossary entry — used inside prose rather than SectionContent columns */
export const GlossaryInlineSchema = z
	.object({
		term: z.string(),
		definition: z.string()
	})
	.passthrough();

export const InsightStripSchema = z
	.object({
		cells: z.array(
			z.object({
				label: z.string(),
				value: z.string(),
				note: z.string().optional(),
				highlight: z.boolean().optional()
			})
		)
	})
	.passthrough();

export const KeyFactSchema = z
	.object({
		fact: z.string(),
		formula: z.string().optional(),
		context: z.string().optional(),
		source: z.string().optional()
	})
	.passthrough();

export const ComparisonGridSchema = z
	.object({
		title: z.string(),
		intro: z.string().optional(),
		columns: z.array(
			z.object({
				id: z.string(),
				title: z.string(),
				summary: z.string(),
				badge: z.string().optional(),
				detail: z.string().optional(),
				highlight: z.boolean().optional()
			})
		),
		rows: z.array(
			z.object({
				criterion: z.string(),
				values: z.array(z.string()),
				takeaway: z.string().optional()
			})
		),
		apply_prompt: z.string().optional()
	})
	.passthrough();

const WorkedStepSchema = z
	.object({
		label: z.string(),
		content: z.string(),
		note: z.string().optional(),
		formula: z.string().optional(),
		diagram_ref: z.string().optional()
	})
	.passthrough();

export const DiagramContentSchema = z
	.object({
		svg_content: z.string().optional(),
		image_url: z.string().optional(),
		caption: z.string(),
		zoom_label: z.string().optional(),
		alt_text: z.string(),
		callouts: z
			.array(
				z.object({
					id: z.string(),
					x: z.number(),
					y: z.number(),
					label: z.string(),
					explanation: z.string()
				})
			)
			.optional(),
		figure_number: z.number().optional(),
		figure_ref: z.string().optional(),
		description: z.string().optional()
	})
	.passthrough();

export const WorkedExampleSchema: z.ZodType<any> = z.lazy(() =>
	z
		.object({
			title: z.string(),
			setup: z.string(),
			steps: z.array(WorkedStepSchema).min(1).max(12),
			conclusion: z.string(),
			method_label: z.string().optional(),
			alternative: WorkedExampleSchema.optional(),
			answer: z.string().optional(),
			alternatives: z.array(z.string()).optional(),
			diagram: DiagramContentSchema.optional()
		})
		.passthrough()
);

export const ProcessSchema = z
	.object({
		title: z.string(),
		intro: z.string().optional(),
		steps: z.array(
			z.object({
				number: z.number(),
				action: z.string(),
				detail: z.string(),
				input: z.string().optional(),
				output: z.string().optional(),
				warning: z.string().optional()
			})
		),
		checklist_mode: z.boolean().optional()
	})
	.passthrough();

export const PracticeSchema = z
	.object({
		problems: z.array(
			z.object({
				difficulty: DifficultySchema,
				problem_type: z.enum(['structured', 'open']).optional(),
				question: z.string(),
				hints: z.array(
					z.object({
						level: HintLevelSchema,
						text: z.string()
					})
				),
				solution: z
					.object({
						approach: z.string(),
						answer: z.string(),
						worked: z.string().optional()
					})
					.optional(),
				writein_lines: z.number().optional(),
				self_assess: z.boolean().optional(),
				context: z.string().optional(),
				diagram: DiagramContentSchema.optional()
			})
		),
		hints_visible_default: z.boolean().optional(),
		solutions_available: z.boolean().optional(),
		label: z.string().optional()
	})
	.passthrough();

export const QuizSchema = z
	.object({
		question: z.string(),
		quiz_type: z.enum(['multiple-choice', 'true-false']).optional(),
		options: z.array(
			z.object({
				text: z.string(),
				correct: z.boolean(),
				explanation: z.string(),
				diagnoses: z.string().optional()
			})
		),
		feedback_correct: z.string(),
		feedback_incorrect: z.string(),
		show_explanations: z.boolean().optional()
	})
	.passthrough();

export const AnswerKeySchema = z
	.object({
		label: z.string().optional(),
		note: z.string().optional(),
		entries: z.array(
			z
				.object({
					question_number: z.number(),
					question: z.string(),
					correct_answer: z.string(),
					correct_key: z.string().optional(),
					diagnostics: z
						.array(
							z
								.object({
									option_key: z.string().optional(),
									option_text: z.string(),
									misconception_id: z.string(),
									misconception_label: z.string()
								})
								.passthrough()
						)
						.optional()
				})
				.passthrough()
		)
	})
	.passthrough();

export const ReflectionSchema = z
	.object({
		prompt: z.string(),
		type: z.enum([
			'open',
			'pair-share',
			'sentence-stem',
			'timed',
			'connect',
			'predict',
			'transfer'
		]),
		space: z.number().optional(),
		sentence_stem: z.string().optional(),
		time_minutes: z.number().optional(),
		pair_instruction: z.string().optional()
	})
	.passthrough();

export const StudentTextboxSchema = z
	.object({
		prompt: z.string(),
		lines: z.number().optional(),
		label: z.string().optional()
	})
	.passthrough();

export const ShortAnswerSchema = z
	.object({
		question: z.string(),
		marks: z.number().optional(),
		lines: z.number().optional(),
		mark_scheme: z.string().optional()
	})
	.passthrough();

export const FillInBlankSchema = z
	.object({
		instruction: z.string().optional(),
		segments: z.array(
			z.object({
				text: z.string(),
				is_blank: z.boolean(),
				answer: z.string().optional()
			})
		),
		word_bank: z.array(z.string()).optional()
	})
	.passthrough();

export const PitfallSchema = z
	.object({
		misconception: z.string(),
		correction: z.string(),
		label: z.string().optional(),
		example: z.string().optional(),
		severity: z.enum(['minor', 'major']).optional(),
		examples: z.array(z.string()).optional(),
		why: z.string().optional()
	})
	.passthrough();

export const DiagramCompareSchema = z
	.object({
		before_svg: z.string().optional(),
		after_svg: z.string().optional(),
		before_image_url: z.string().optional(),
		after_image_url: z.string().optional(),
		before_label: z.string(),
		after_label: z.string(),
		before_details: z.array(z.string()).optional(),
		after_details: z.array(z.string()).optional(),
		caption: z.string(),
		alt_text: z.string()
	})
	.passthrough();

export const DiagramSeriesSchema = z
	.object({
		title: z.string(),
		diagrams: z.array(
			z.object({
				step_label: z.string(),
				caption: z.string(),
				svg_content: z.string().optional(),
				image_url: z.string().optional()
			})
		)
	})
	.passthrough();

export const VideoEmbedSchema = z
	.object({
		media_id: z.string(),
		caption: z.string().optional(),
		start_time: z.number().optional(),
		end_time: z.number().optional(),
		print_fallback: z.enum(['thumbnail', 'qr-link', 'hide'])
	})
	.passthrough();

export const ImageBlockSchema = z
	.object({
		media_id: z.string(),
		caption: z.string().optional(),
		alt_text: z.string(),
		width: z.enum(['full', 'half', 'third']).optional(),
		alignment: z.enum(['left', 'center', 'right']).optional()
	})
	.passthrough();

export const TimelineSchema = z
	.object({
		title: z.string(),
		intro: z.string().optional(),
		events: z.array(
			z.object({
				id: z.string(),
				era: z.string().optional(),
				year: z.string(),
				title: z.string(),
				summary: z.string(),
				impact: z.string().optional(),
				tags: z.array(z.string()).optional()
			})
		),
		closing_takeaway: z.string().optional()
	})
	.passthrough();

const InteractionSpecSchema = z
	.object({
		type: z.string(),
		goal: z.string(),
		anchor_content: z.record(z.string(), z.unknown()),
		context: z.object({
			learner_level: z.string(),
			template_id: z.string(),
			color_mode: z.enum(['light', 'dark']),
			accent_color: z.string(),
			surface_color: z.string(),
			font_mono: z.string()
		}),
		dimensions: z.object({
			width: z.string(),
			height: z.number(),
			resizable: z.boolean()
		}),
		print_translation: z.enum(['static_midstate', 'static_diagram', 'hide'])
	})
	.passthrough();

export const SimulationSchema = z
	.object({
		spec: InteractionSpecSchema,
		html_content: z.string().optional(),
		fallback_diagram: DiagramContentSchema.optional(),
		explanation: z.string().optional()
	})
	.passthrough();

export const SCHEMA_BY_SECTION_FIELD = {
	header: SectionHeaderSchema,
	hook: HookHeroSchema,
	explanation: ExplanationSchema,
	prerequisites: PrerequisiteSchema,
	what_next: WhatNextSchema,
	interview: InterviewSchema,
	callout: CalloutBlockSchema,
	summary: SummaryBlockSchema,
	divider: DividerSchema,
	definition: DefinitionSchema,
	definition_family: DefinitionFamilySchema,
	glossary: GlossarySchema,
	insight_strip: InsightStripSchema,
	key_fact: KeyFactSchema,
	comparison_grid: ComparisonGridSchema,
	worked_example: WorkedExampleSchema,
	process: ProcessSchema,
	practice: PracticeSchema,
	quiz: QuizSchema,
	answer_key: AnswerKeySchema,
	reflection: ReflectionSchema,
	student_textbox: StudentTextboxSchema,
	short_answer: ShortAnswerSchema,
	fill_in_blank: FillInBlankSchema,
	pitfall: PitfallSchema,
	diagram: DiagramContentSchema,
	diagram_compare: DiagramCompareSchema,
	diagram_series: DiagramSeriesSchema,
	video_embed: VideoEmbedSchema,
	image_block: ImageBlockSchema,
	timeline: TimelineSchema,
	simulation: SimulationSchema
} as const;

export type LectioSectionFieldKey = keyof typeof SCHEMA_BY_SECTION_FIELD;

export function getSectionFieldSchema(sectionField: string | null): z.ZodTypeAny | undefined {
	if (sectionField === null) return undefined;
	return SCHEMA_BY_SECTION_FIELD[sectionField as LectioSectionFieldKey] as z.ZodTypeAny | undefined;
}
