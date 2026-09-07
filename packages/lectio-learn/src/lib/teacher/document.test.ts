import { describe, expect, it } from 'vitest';

import { calculusSection, physicsSection } from '../dev/dummy-content';
import type { SectionContent } from '../schema/types';
import { fromSectionContents, toSectionContents, validateDocument } from './document';

describe('LessonDocument conversion', () => {
	it('round-trips a rich section through fromSectionContents and toSectionContents', () => {
		const doc = fromSectionContents([calculusSection], {
			title: calculusSection.header!.title,
			subject: calculusSection.header!.subject,
			preset_id: 'blue-classroom',
			source: 'template',
			grade_band: calculusSection.header!.grade_band
		});

		expect(doc.version).toBe(1);
		expect(doc.sections).toHaveLength(1);
		expect(doc.sections[0].id).toBe(calculusSection.section_id);

		const back = toSectionContents(doc)[0];
		expect(back).toEqual(calculusSection);
	});

	it('validateDocument passes for a converted document', () => {
		const doc = fromSectionContents([calculusSection], {
			title: 'T',
			subject: 'Mathematics',
			preset_id: 'blue-classroom',
			source: 'generated',
			source_generation_id: 'gen-1'
		});
		const result = validateDocument(doc);
		expect(result.valid).toBe(true);
		expect(result.errors).toHaveLength(0);
	});

	it('validateDocument reports structural errors', () => {
		const doc = fromSectionContents([calculusSection], {
			title: 'T',
			subject: 'Mathematics',
			preset_id: 'blue-classroom'
		});
		doc.sections[0].block_ids.push('missing-block');
		const result = validateDocument(doc);
		expect(result.valid).toBe(false);
		expect(result.errors.some((e) => e.includes('missing-block'))).toBe(true);
	});

	it('round-trips a diagnostic answer key as a registered block', () => {
		const section: SectionContent = {
			section_id: 'teacher-key',
			template_id: 'open-canvas',
			answer_key: {
				entries: [
					{
						question_number: 1,
						question: 'Where did most of the tree mass come from?',
						correct_answer: 'carbon dioxide from the air',
						diagnostics: [
							{
								option_text: 'minerals from the soil',
								misconception_id: 'M1',
								misconception_label: 'mass comes from the soil'
							}
						]
					}
				]
			}
		};

		const doc = fromSectionContents([section], {
			title: 'Teacher key',
			subject: 'Biology',
			preset_id: 'blue-classroom'
		});
		const answerKeyBlock = Object.values(doc.blocks).find(
			(block) => block.component_id === 'answer-key'
		);

		expect(answerKeyBlock?.content).toEqual(section.answer_key);
		expect(toSectionContents(doc)[0].answer_key).toEqual(section.answer_key);
	});

	it('emits at most one simulation-block per section from singular simulation', () => {
		const section = {
			...physicsSection,
			section_id: 'phys-sim-single'
		};

		const doc = fromSectionContents([section], {
			title: section.header!.title,
			subject: section.header!.subject,
			preset_id: 'blue-classroom'
		});
		const simulationBlocks = Object.values(doc.blocks).filter(
			(block) => block.component_id === 'simulation-block'
		);

		expect(simulationBlocks).toHaveLength(1);

		const back = toSectionContents(doc)[0];
		expect(back.simulation).toEqual(section.simulation);
	});

	it('keeps only the first simulation-block when a document lists duplicates', () => {
		const secondSimulation = {
			...physicsSection.simulation!,
			explanation: 'A second interaction that should be ignored on load.'
		};
		const section = {
			...physicsSection,
			section_id: 'phys-dup-blocks'
		};

		const doc = fromSectionContents([section], {
			title: section.header!.title,
			subject: section.header!.subject,
			preset_id: 'blue-classroom'
		});

		const blockIds = doc.sections[0].block_ids;
		const firstSimIdx = blockIds.findIndex((id) => doc.blocks[id].component_id === 'simulation-block');
		expect(firstSimIdx).toBeGreaterThanOrEqual(0);

		const templateBlock = doc.blocks[blockIds[firstSimIdx]];
		const dupId = 'dup-simulation-block-test-id';
		doc.blocks[dupId] = {
			...templateBlock,
			id: dupId,
			content: structuredClone(secondSimulation) as Record<string, unknown>,
			position: templateBlock.position + 0.5
		};
		blockIds.splice(firstSimIdx + 1, 0, dupId);

		const validated = validateDocument(doc);
		expect(validated.warnings.some((w) => w.includes('only the first is loaded'))).toBe(true);

		const back = toSectionContents(doc)[0];
		expect(back.simulation).toEqual(section.simulation);
		expect(back.simulation?.explanation).not.toEqual(secondSimulation.explanation);
	});
});
