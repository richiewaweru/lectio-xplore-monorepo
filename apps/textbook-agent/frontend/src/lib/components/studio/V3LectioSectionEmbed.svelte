<script lang="ts">
	import { LectioThemeSurface, basePresetMap, templateRegistryMap } from 'lectio';
	import type { SectionContent } from 'lectio';

	function sanitizeMerged(fields: Record<string, unknown>): Record<string, unknown> {
		const next = { ...fields };
		const practice = next.practice as Record<string, unknown> | undefined;
		if (practice && Array.isArray(practice.problems)) {
			practice.problems = practice.problems.map((raw) => {
				if (typeof raw !== 'object' || raw === null) return raw;
				const { _qid: _, ...rest } = raw as Record<string, unknown>;
				return rest;
			});
			next.practice = practice;
		}
		return next;
	}

	interface Props {
		templateId: string;
		sectionId: string;
		title: string;
		mergedFields: Record<string, unknown>;
	}

	let { templateId, sectionId, title, mergedFields }: Props = $props();

	const template = $derived(templateRegistryMap[templateId]);
	const preset = $derived(basePresetMap['blue-classroom'] ?? Object.values(basePresetMap)[0]);
	const sectionView = $derived(
		({
			section_id: sectionId,
			header: { title },
			...sanitizeMerged(mergedFields)
		}) as SectionContent
	);
</script>

{#if template && preset && Object.keys(mergedFields).length > 0}
	<div class="v3-lectio-embed rounded-xl border border-border/60 bg-card p-4 shadow-sm">
		<LectioThemeSurface {preset}>
			{@const R = template.render}
			<R section={sectionView} />
		</LectioThemeSurface>
	</div>
{/if}
