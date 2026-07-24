import type { DocumentSection, LessonDocument } from 'lectio';

export type BuilderIssue = {
	id: string;
	severity: string;
	message: string;
	kind: string;
	target_block_id?: string;
	generated_ref?: string;
	component_ref?: string;
	visual_id?: string;
	repair_target_id?: string;
	resolved: boolean;
};

export type BlockAiRepairRequest = {
	requestKey: string;
	issueId: string;
	sectionId: string;
	targetBlockId: string;
	initialInstruction: string;
};

export type IssueSection = DocumentSection & { meta?: { issues?: BuilderIssue[] } };

export function issuesForSection(section: DocumentSection): BuilderIssue[] {
	return (section as IssueSection).meta?.issues ?? [];
}

export function unresolvedIssues(document: LessonDocument): BuilderIssue[] {
	return document.sections.flatMap(issuesForSection).filter((issue) => !issue.resolved);
}
