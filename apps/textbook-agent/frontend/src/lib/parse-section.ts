import { z } from 'zod';
import type { SectionContent } from 'lectio';

const SectionContentSchema = z
	.object({
		section_id: z.string().min(1),
		template_id: z.string().min(1),
		header: z.object({
			title: z.string(),
			subject: z.string(),
			grade_band: z.enum(['primary', 'secondary', 'advanced'])
		}),
		hook: z.object({
			headline: z.string(),
			body: z.string(),
			anchor: z.string()
		}),
		explanation: z.object({
			body: z.string(),
			emphasis: z.array(z.string())
		}),
		practice: z.object({
			problems: z
				.array(
					z.object({
						difficulty: z.enum(['warm', 'medium', 'cold', 'extension']),
						question: z.string(),
						hints: z.array(
							z.object({
								level: z.union([z.literal(1), z.literal(2), z.literal(3)]),
								text: z.string()
							})
						)
					})
				)
				.min(2)
				.max(5)
		}),
		what_next: z.object({
			body: z.string(),
			next: z.string()
		})
	})
	.passthrough();

export function parseIncomingSection(raw: unknown): SectionContent {
	const result = SectionContentSchema.safeParse(raw);
	if (!result.success) {
		const first = result.error.issues[0];
		throw new Error(
			`[Lectio] Invalid section from pipeline at '${first.path.join('.')}': ${first.message}`
		);
	}
	return result.data as SectionContent;
}
