import type { ZodIssue, ZodTypeAny } from 'zod';

import { isContentContractEligible } from '$lib/lectio/export-policy';
import type { LectioComponentModule } from './types';

type ValidatableModule = Pick<
	LectioComponentModule,
	'schema' | 'metadata' | 'print' | 'examples' | 'contentContract'
>;

const PHASES = new Set<number>([1, 2, 3, 4, 5, 6, 7]);

export interface LectioComponentValidationIssue {
	readonly path: string;
	readonly message: string;
	readonly severity?: 'error' | 'warn';
}

export function validateLectioContentModule(module: ValidatableModule): LectioComponentValidationIssue[] {
	const issues: LectioComponentValidationIssue[] = [];
	const m = module.metadata;
	const prefix = `[${m.registryKey}:${m.id}]`;

	if (!m.id.trim()) issues.push({ path: 'metadata.id', message: `${prefix} Missing metadata.id` });
	if (!m.name.trim())
		issues.push({ path: 'metadata.name', message: `${prefix} Missing metadata.name` });
	if (!m.role.trim()) issues.push({ path: 'metadata.role', message: `${prefix} Missing metadata.role` });
	if (!m.registryKey.trim()) {
		issues.push({ path: 'metadata.registryKey', message: `${prefix} Missing metadata.registryKey` });
	}

	if (!PHASES.has(m.phase))
		issues.push({ path: 'metadata.phase', message: `${prefix} phase must be 1–7` });

	if (!(m.sectionField === null || typeof m.sectionField === 'string'))
		issues.push({ path: 'metadata.sectionField', message: `${prefix} metadata.sectionField must be string|null` });

	if (isContentContractEligible(module)) {
		if (!module.contentContract) {
			issues.push({
				path: 'contentContract',
				message: `${prefix} contentContract is required for generation-facing exports`,
				severity: 'error'
			});
		} else {
			if (module.contentContract.componentId !== m.id) {
				issues.push({
					path: 'contentContract.componentId',
					message: `${prefix} contentContract.componentId must match metadata.id`,
					severity: 'error'
				});
			}
			if (module.contentContract.sectionField !== m.sectionField) {
				issues.push({
					path: 'contentContract.sectionField',
					message: `${prefix} contentContract.sectionField must match metadata.sectionField`,
					severity: 'error'
				});
			}

			const fieldContracts = module.contentContract.fieldContracts ?? {};
			const fcKeys = Object.keys(fieldContracts);
			const onlyGenericContentPlaceholder =
				fcKeys.length === 1 &&
				fcKeys[0] === 'content' &&
				fieldContracts.content?.format === 'structured_object' &&
				fieldContracts.content?.description?.includes('Schema-aligned content payload');

			if (
				(m.status === 'stable' || m.status === 'beta') &&
				onlyGenericContentPlaceholder
			) {
				issues.push({
					path: 'contentContract.fieldContracts',
					message: `${prefix} contentContract uses a generic placeholder; replace with field-level behavior for stable exports`,
					severity: 'warn'
				});
			}

			if (m.id === 'diagram-block') {
				const needed = ['image_url', 'caption', 'alt_text', 'callouts'];
				const missing = needed.filter((key) => !fieldContracts[key]);
				if (missing.length) {
					issues.push({
						path: 'contentContract.fieldContracts',
						message: `${prefix} diagram-block contract should document: ${needed.join(', ')} (missing: ${missing.join(', ')})`,
						severity: 'warn'
					});
				}
			}
		}
	}

	const print = module.print;
	const breakBehaviors = new Set(['atomic', 'itemized', 'table', 'prose']);
	const preferredWidths = new Set(['full', 'half', 'third', 'content-fit', 'inline', 'aside']);
	const mediaConstraints = new Set(['constrain-height', 'constrain-width', 'fit-cell']);

	if (!breakBehaviors.has(print.breakBehavior)) {
		issues.push({
			path: 'print.breakBehavior',
			message: `${prefix} print.breakBehavior must be atomic|itemized|table|prose`
		});
	}

	if (!preferredWidths.has(print.preferredWidth)) {
		issues.push({
			path: 'print.preferredWidth',
			message: `${prefix} print.preferredWidth must be full|half|third|content-fit|inline|aside`
		});
	}

	if (!(typeof print.fallback === 'string' && print.fallback.trim().length > 0)) {
		issues.push({ path: 'print.fallback', message: `${prefix} print.fallback missing` });
	}

	if (typeof print.hasMedia !== 'boolean') {
		issues.push({ path: 'print.hasMedia', message: `${prefix} print.hasMedia must be boolean` });
	}

	if (typeof print.requiresColorReset !== 'boolean') {
		issues.push({
			path: 'print.requiresColorReset',
			message: `${prefix} print.requiresColorReset must be boolean`
		});
	}

	if (print.mediaConstraint !== undefined && !mediaConstraints.has(print.mediaConstraint)) {
		issues.push({
			path: 'print.mediaConstraint',
			message: `${prefix} print.mediaConstraint must be constrain-height|constrain-width|fit-cell`
		});
	}

	if (print.breakBehavior === 'itemized') {
		if (!(typeof print.itemSelector === 'string' && print.itemSelector.trim().length > 0)) {
			issues.push({
				path: 'print.itemSelector',
				message: `${prefix} print.itemSelector is required when breakBehavior is itemized`
			});
		} else if (!print.itemSelector.trim().startsWith('.')) {
			issues.push({
				path: 'print.itemSelector',
				message: `${prefix} print.itemSelector should be a class selector starting with '.'`
			});
		}
	}

	if (!(module.schema && typeof module.schema === 'object' && 'safeParse' in module.schema)) {
		issues.push({
			path: 'schema',
			message: `${prefix} schema missing or invalid`
		});
	}

	const schemaPresent = !!(module.schema && typeof module.schema === 'object' && 'safeParse' in module.schema);

	if (!Array.isArray(module.examples)) {
		issues.push({ path: 'examples', message: `${prefix} examples must be an array` });
	} else if (schemaPresent && m.sectionField !== null) {
		module.examples.forEach((example, idx) => {
			const typedSchema = module.schema as ZodTypeAny;
			const parsed = typedSchema.safeParse(example);
			if (!parsed.success) {
				appendZodIssues(issues, prefix, parsed.error.issues, `examples.${idx}`);
			}
		});
	} else if (schemaPresent && m.sectionField === null) {
		// Inline-only components validate examples against exported schema slice (inline props)
		module.examples.forEach((example, idx) => {
			const typedSchema = module.schema as ZodTypeAny;
			const parsed = typedSchema.safeParse(example);
			if (!parsed.success) {
				appendZodIssues(issues, prefix, parsed.error.issues, `examples.${idx}`);
			}
		});
	}

	return issues;
}

function appendZodIssues(
	issues: LectioComponentValidationIssue[],
	modulePrefix: string,
	zissues: readonly ZodIssue[],
	basePath: string
): void {
	for (const issue of zissues) {
		const pathTail = issue.path.filter((p): p is string | number => p !== '').join('.');
		const resolved = pathTail ? `${basePath}.${pathTail}` : basePath;
		issues.push({
			path: resolved,
			message: `${modulePrefix} ${resolved}: ${issue.message}`
		});
	}
}

export function validateAllLectioContentModules(modules: readonly ValidatableModule[]): LectioComponentValidationIssue[] {
	return modules.flatMap((m) => validateLectioContentModule(m));
}
