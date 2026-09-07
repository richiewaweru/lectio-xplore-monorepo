<script lang="ts">
	import { Badge } from '$lib/components/ui/badge';
	import { Button } from '$lib/components/ui/button';
	import { Card } from '$lib/components/ui/card';
	import type {
		InteractionLevel,
		LearnerFit,
		LessonIntent,
		TemplateContract,
		TemplateFamily
	} from '$lib/templates/types';

	const familyLabels: Record<TemplateFamily, string> = {
		'guided-concept': 'Guided Concept',
		'visual-exploration': 'Visual Exploration',
		'compare-distinguish': 'Compare and Distinguish',
		'narrative-timeline': 'Narrative and Timeline',
		'process-procedure': 'Process and Procedure',
		'focus-accommodation': 'Focus and Accommodation'
	};

	const intentLabels: Record<LessonIntent, string> = {
		'introduce-concept': 'New concept',
		'explain-visually': 'Visual-first',
		'compare-ideas': 'Comparison',
		'teach-sequence': 'Narrative',
		'teach-procedure': 'Procedure',
		'reduce-overload': 'Support / SPED',
		'reinforce-learning': 'Revision',
		'build-rigor': 'Deep dive'
	};

	const learnerLabels: LearnerFit[] = [
		'general',
		'visual',
		'analytical',
		'narrative',
		'adhd-friendly',
		'dyslexia-sensitive',
		'scaffolded',
		'advanced'
	];

	const interactionLabels: InteractionLevel[] = ['none', 'light', 'medium', 'high'];

	let { templates }: { templates: TemplateContract[] } = $props();

	let family = $state<TemplateFamily | undefined>(undefined);
	let intent = $state<LessonIntent | undefined>(undefined);
	let learnerFit = $state<LearnerFit | undefined>(undefined);
	let subject = $state<string | undefined>(undefined);
	let interactionLevel = $state<InteractionLevel | undefined>(undefined);

	const subjects = $derived(
		Array.from(new Set(templates.flatMap((template) => template.subjects))).sort((a, b) =>
			a.localeCompare(b)
		)
	);

	const filtered = $derived(
		templates.filter((template) => {
			if (family && template.family !== family) {
				return false;
			}

			if (intent && template.intent !== intent) {
				return false;
			}

			if (learnerFit && !template.learnerFit.includes(learnerFit)) {
				return false;
			}

			if (
				subject &&
				!template.subjects.some((entry) => entry.toLowerCase() === subject?.toLowerCase())
			) {
				return false;
			}

			if (interactionLevel && template.interactionLevel !== interactionLevel) {
				return false;
			}

			return true;
		})
	);

	const families = Object.keys(familyLabels) as TemplateFamily[];
	const visibleFamilies = $derived(
		families
			.map((familyKey) => ({
				family: familyKey,
				items: filtered.filter((template) => template.family === familyKey)
			}))
			.filter((group) => group.items.length > 0)
	);

	function toggleFilter<T extends string>(current: T | undefined, next: T) {
		return current === next ? undefined : next;
	}
</script>

{#snippet filterRow<T extends string>(
	label: string,
	options: T[],
	active: T | undefined,
	onToggle: (value: T | undefined) => void,
	renderLabel: (value: T) => string
)}
	<div class="flex flex-wrap items-center gap-2">
		<span class="text-sm font-semibold text-primary">{label}</span>
		<Button
			variant={active === undefined ? 'default' : 'outline'}
			class="rounded-full"
			onclick={() => onToggle(undefined)}
		>
			All
		</Button>
		{#each options as option}
			<Button
				variant={active === option ? 'default' : 'outline'}
				class="rounded-full"
				onclick={() => onToggle(toggleFilter(active, option))}
			>
				{renderLabel(option)}
			</Button>
		{/each}
	</div>
{/snippet}

<div class="space-y-8">
	<div class="lesson-shell rh-pad-shell">
		<div class="relative z-10 space-y-5">
			<div class="rh-gap-component-tight">
				<p class="eyebrow">Template gallery</p>
				<h1 class="text-4xl text-primary font-serif sm:text-5xl">
					Six teaching families. Filter to find your match.
				</h1>
				<p class="max-w-3xl text-lg leading-8 text-muted-foreground">
					Each template is a structural teaching strategy, not just a look. Filter by
					intent, learner fit, subject, and interaction level to narrow the field.
				</p>
			</div>

			<div class="rh-gap-component-tight">
				{@render filterRow(
					'Intent',
					Object.keys(intentLabels) as LessonIntent[],
					intent,
					(value) => (intent = value),
					(value) => intentLabels[value]
				)}
				{@render filterRow('Learner', learnerLabels, learnerFit, (value) => (learnerFit = value), (value) => value)}
				{@render filterRow('Subject', subjects, subject, (value) => (subject = value), (value) => value)}
				{@render filterRow(
					'Interaction',
					interactionLabels,
					interactionLevel,
					(value) => (interactionLevel = value),
					(value) => value
				)}
				{@render filterRow(
					'Family',
					families,
					family,
					(value) => (family = value),
					(value) => familyLabels[value]
				)}
			</div>

			<div class="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
				<Badge class="bg-primary/10 text-primary hover:bg-primary/10">
					Showing {filtered.length} templates
				</Badge>
				<span>across {visibleFamilies.length} families.</span>
				<span>All templates print cleanly regardless of interaction level.</span>
			</div>
		</div>
	</div>

	{#if visibleFamilies.length === 0}
		<Card class="border-dashed bg-white/75 p-8 text-center text-muted-foreground">
			No templates match these filters. Try broadening your selection.
		</Card>
	{/if}

	{#each visibleFamilies as group}
		<section class="rh-gap-component">
			<div class="flex flex-wrap items-end justify-between rh-gap-cluster">
				<div class="space-y-1">
					<p class="eyebrow">{familyLabels[group.family]}</p>
					<h2 class="text-3xl text-primary font-serif">
						{group.items.length} template{group.items.length === 1 ? '' : 's'}
					</h2>
				</div>
				<p class="max-w-2xl text-sm leading-6 text-muted-foreground">
					{group.items[0]?.whyThisTemplateExists}
				</p>
			</div>

			<div class="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
				{#each group.items as template}
					<Card class="border-white/60 bg-white/82 rh-pad-card">
						<div class="rh-gap-component">
							<div class="flex flex-wrap gap-2">
								<Badge class="bg-primary/10 text-primary hover:bg-primary/10">
									{familyLabels[template.family]}
								</Badge>
								<Badge variant="outline">{template.interactionLevel}</Badge>
								<Badge variant="outline">{template.readingStyle}</Badge>
							</div>

							<div class="space-y-2">
								<h3 class="text-2xl text-primary font-serif">{template.name}</h3>
								<p class="text-base leading-7 text-muted-foreground">{template.tagline}</p>
							</div>

							<div class="flex flex-wrap gap-2">
								{#each template.learnerFit as fit}
									<Badge variant="outline">{fit}</Badge>
								{/each}
							</div>
							<div class="flex flex-wrap gap-2">
								{#each template.subjects as templateSubject}
									<Badge class="bg-secondary text-secondary-foreground hover:bg-secondary">
										{templateSubject}
									</Badge>
								{/each}
							</div>
							<div class="flex flex-wrap gap-2">
								{#each template.tags as tag}
									<Badge variant="outline" class="border-dashed">{tag}</Badge>
								{/each}
							</div>

							<div class="flex flex-wrap gap-1">
								{#each template.always_present as component}
									<span class="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">{component}</span>
								{/each}
							</div>

							<a
								href={`/templates/${template.id}`}
								class="inline-flex w-full items-center justify-center rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
							>
								Use this template
							</a>
						</div>
					</Card>
				{/each}
			</div>
		</section>
	{/each}
</div>
