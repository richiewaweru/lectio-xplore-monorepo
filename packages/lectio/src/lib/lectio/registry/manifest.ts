import { LECTIO_PHASES } from '$lib/lectio/core/phases';
import { teacherFor } from '$lib/teacher/teacher-facing';

import { lectioComponentModules } from './components';

export interface LectioManifestV3 {
	version: string;
	phases: Record<
		string,
		(typeof LECTIO_PHASES)[keyof typeof LECTIO_PHASES] & {
			components: Array<Record<string, unknown>>;
		}
	>;
}

export function buildLectioManifest(): LectioManifestV3 {
	const phasesEntries = Object.entries(LECTIO_PHASES).map(([phaseId, phase]) => [
		phaseId,
		{
			...phase,
			components: lectioComponentModules
				.filter((component) => component.metadata.phase === Number(phaseId))
				.map((component) => {
					const teacher = teacherFor(component.metadata.id);
					return {
						id: component.metadata.id,
						name: component.metadata.name,
						teacher_label: teacher.teacherLabel,
						teacher_description: teacher.teacherDescription,
						cognitive_job: component.metadata.cognitiveJob,
						role: component.metadata.role,
						subjects: component.metadata.subjects,
						behaviour_modes: component.metadata.behaviourModes,
						capabilities: component.metadata.capabilities,
						capacity: component.metadata.capacity,
						section_field: component.metadata.sectionField,
						status: component.metadata.status,
						print: component.print,
						shadcn_primitive: component.metadata.shadcnPrimitive
					};
				})
		}
	]);

	return {
		version: '3.0.0',
		phases: Object.fromEntries(phasesEntries) as LectioManifestV3['phases']
	};
}
