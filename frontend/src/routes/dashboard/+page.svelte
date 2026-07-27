<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { fromStore } from 'svelte/store';
	import { isApiError } from '$lib/api/errors';
	import { getOnboardingRoute, resolveDashboardProfileFailure } from '$lib/auth/routing';
	import { fetchV3Document, getV3Generations } from '$lib/api/v3';
	import { getPacks } from '$lib/api/learning-pack';
	import { friendlyGenerationErrorMessage } from '$lib/generation/error-messages';
	import { getProfile } from '$lib/api/profile';
	import { v3PackToBuilderDocument } from '$lib/builder/adapters/from-generation';
	import { createBuilderLesson, listBuilderLessons, type BuilderLessonSummary } from '$lib/builder/api/lesson-crud';
	import { saveDocument } from '$lib/builder/persistence/idb-store';
	import { getStreamIntoBuilder, setStreamIntoBuilder } from '$lib/settings/flags';
	import { authUser, logout } from '$lib/stores/auth';
	import ProfileSummary from '$lib/components/workspace/ProfileSummary.svelte';
	import type { TeacherProfile } from '$lib/types';
	import type { V3GenerationHistoryItem } from '$lib/types/v3';
	import type { PackStatusResponse } from '$lib/types/learning-pack';
	import type { V3PackDocument } from '$lib/studio/v3-pack-to-lectio-document';

	const user = fromStore(authUser);

	let profile = $state<TeacherProfile | null>(null);
	let v3Generations = $state<V3GenerationHistoryItem[]>([]);
	let recentPacks = $state<PackStatusResponse[]>([]);
	let builderLessons = $state<BuilderLessonSummary[]>([]);
	let loadingProfile = $state(true);
	let profileErrorMessage = $state<string | null>(null);
	let openingBuilderId = $state<string | null>(null);
	let builderOpenError = $state<string | null>(null);
	let streamIntoBuilder = $state(false);

	onMount(async () => {
		streamIntoBuilder = getStreamIntoBuilder();
		try {
			profile = await getProfile();
		} catch (err) {
			const resolution = resolveDashboardProfileFailure(err, {
				hasProfileHint: user.current?.has_profile ?? false
			});
			if (resolution.redirectTo) {
				if (resolution.redirectTo === '/login') {
					logout();
				}
				goto(resolution.redirectTo, { replaceState: true });
				return;
			}
			profileErrorMessage = resolution.message ?? 'Failed to load your profile.';
			return;
		} finally {
			loadingProfile = false;
		}

		try {
			const [generations, packs, lessons] = await Promise.all([
				getV3Generations(),
				getPacks(),
				streamIntoBuilder ? listBuilderLessons() : Promise.resolve([])
			]);
			v3Generations = generations;
			recentPacks = packs;
			builderLessons = lessons;
		} catch (err) {
			if (isApiError(err) && err.status === 401) {
				logout();
				goto('/login', { replaceState: true });
			}
		}
	});

	function v3OpenRoute(generationId: string): string {
		return `/studio/generations/${generationId}`;
	}

	function generationForLesson(lesson: BuilderLessonSummary): V3GenerationHistoryItem | undefined {
		return lesson.source_generation_id
			? v3Generations.find((generation) => generation.id === lesson.source_generation_id)
			: undefined;
	}

	function lessonStatus(lesson: BuilderLessonSummary): { symbol: string; label: string; tone: string } {
		const generation = generationForLesson(lesson);
		if (generation && generation.status !== 'completed' && generation.status !== 'failed') {
			return { symbol: '●', label: 'streaming', tone: 'running' };
		}
		if (generation?.status === 'completed') return { symbol: '✓', label: 'complete', tone: 'completed' };
		return { symbol: '✎', label: 'draft', tone: 'pending' };
	}

	function builderLessonRoute(lesson: BuilderLessonSummary): string {
		const generation = generationForLesson(lesson);
		return generation && lessonStatus(lesson).label === 'streaming'
			? `/builder/${lesson.id}?generation_id=${generation.id}`
			: `/builder/${lesson.id}`;
	}

	const generationsWithoutBuilder = $derived(
		v3Generations.filter(
			(generation) => !builderLessons.some((lesson) => lesson.source_generation_id === generation.id)
		)
	);

	async function openGenerationInBuilder(generationId: string, title: string): Promise<void> {
		openingBuilderId = generationId;
		builderOpenError = null;
		try {
			const pack = (await fetchV3Document(generationId)) as V3PackDocument;
			const lesson = v3PackToBuilderDocument(pack, {
				routeGenerationId: generationId
			});
			const created = await createBuilderLesson({
				source_type: 'v3_generation',
				source_generation_id: generationId,
				title: title || lesson.title,
				document: lesson
			});
			await saveDocument(created.document);
			await goto(`/builder/${created.id}`);
		} catch (err) {
			builderOpenError = err instanceof Error ? err.message : 'Failed to open lesson in builder.';
		} finally {
			openingBuilderId = null;
		}
	}
</script>

<div class="dashboard">
	{#if loadingProfile}
		<p>Loading your profile...</p>
	{:else if profileErrorMessage}
		<div class="error">
			<p><strong>Error:</strong> {profileErrorMessage}</p>
		</div>
	{:else if profile}
		<section class="welcome-section">
			<div>
				<p class="eyebrow">V3 Studio</p>
				<h1>Welcome back{user.current?.name ? `, ${user.current.name}` : ''}</h1>
				<p class="subtitle">
					Your saved teacher profile powers workspace defaults, while Studio remains the place where each lesson gets planned and generated.
				</p>
			</div>
		</section>

		<ProfileSummary
			{profile}
			{streamIntoBuilder}
			onStreamIntoBuilderChange={(enabled) => {
				streamIntoBuilder = enabled;
				setStreamIntoBuilder(enabled);
			}}
			onEdit={() => goto(getOnboardingRoute({ edit: true }))}
		/>

		<section class="generate-section">
			<h2>Teacher Studio</h2>
			<p>
				The canonical lesson-creation flow now lives in the dedicated studio route. Open it to
				capture intent, narrow the topic, choose the resource shape, and generate the lesson.
			</p>
			<div class="studio-entry studio-entry-prominent">
				<div class="studio-entry-copy">
					<p class="studio-kicker">Canonical flow</p>
					<h3>Create a lesson in Studio</h3>
					<p>
						Teachers now build a structured V3 plan, confirm the scope, and hand a cleaner
						starting point into the generation system.
					</p>
					<div class="studio-features">
						<span>Topic narrowing</span>
						<span>Learner context</span>
						<span>Support selection</span>
					</div>
				</div>
				<div class="studio-entry-actions">
					<a href="/studio" class="studio-link">Open Studio</a>
					<button class="ghost-link" onclick={() => goto('/studio')}>Resume Studio</button>
				</div>
			</div>
		</section>

		<section class="generate-section">
			<h2>Lesson Builder</h2>
			<p>
				Open your editable lesson workspace to continue drafts, refine generated lessons, or start
				a new lesson from template or blank canvas.
			</p>
			<div class="studio-entry">
				<div class="studio-entry-copy">
					<p class="studio-kicker">Teacher-owned editing</p>
					<h3>Manage editable lessons</h3>
					<p>
						See all builder lessons, resume in-progress work, and create new lessons without
						running generation first.
					</p>
				</div>
				<div class="studio-entry-actions">
					<a href="/builder" class="studio-link">Open Builder</a>
					<a href="/builder/new" class="ghost-link">New Lesson</a>
				</div>
			</div>
		</section>

		{#if recentPacks.length > 0}
			<section class="history-section">
				<h2>Recent Packs</h2>
				<ul class="history-list">
					{#each recentPacks as pack}
						<li class="history-item">
							<div class="history-info">
								<p class="history-subject">{pack.topic}</p>
								<div class="history-meta">
									<span class="status status-{pack.status}">{pack.status}</span>
									<span>{pack.subject}</span>
									<span>{pack.completed_count}/{pack.resource_count} ready</span>
								</div>
							</div>
							<div class="history-actions">
								<a href={`/packs/${pack.pack_id}`} class="view-link">Open</a>
							</div>
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		{#if streamIntoBuilder && (builderLessons.length > 0 || generationsWithoutBuilder.length > 0)}
			<section class="history-section">
				<h2>Lessons</h2>
				<ul class="history-list">
					{#each builderLessons as lesson (lesson.id)}
						{@const status = lessonStatus(lesson)}
						<li class="history-item">
							<div class="history-info">
								<p class="history-subject">{lesson.title}</p>
								<div class="history-meta">
									<span class={`status status-${status.tone}`}>{status.symbol} {status.label}</span>
									<span>{lesson.source_type === 'v3_generation' ? 'Generated lesson' : 'Builder draft'}</span>
								</div>
							</div>
							<div class="history-actions"><a href={builderLessonRoute(lesson)} class="view-link">Open</a></div>
						</li>
					{/each}
					{#each generationsWithoutBuilder as gen (gen.id)}
						<li class="history-item">
							<div class="history-info">
								<p class="history-subject">{gen.title || gen.subject}</p>
								<div class="history-meta"><span class={`status status-${gen.status}`}>{gen.status}</span><span>Pre-Builder generation</span></div>
							</div>
							<div class="history-actions">
								<a href={v3OpenRoute(gen.id)} class="view-link">Open</a>
								{#if gen.status === 'completed'}
									<button type="button" class="view-link action-link" disabled={openingBuilderId === gen.id} onclick={() => openGenerationInBuilder(gen.id, gen.title || gen.subject)}>
										{openingBuilderId === gen.id ? 'Opening...' : 'Edit in Builder'}
									</button>
								{/if}
							</div>
						</li>
					{/each}
				</ul>
			</section>
		{:else if !streamIntoBuilder && v3Generations.length > 0}
			<section class="history-section">
				<h2>Saved V3 Books</h2>
				{#if builderOpenError}
					<p class="failure-copy">{builderOpenError}</p>
				{/if}
				<ul class="history-list">
					{#each v3Generations as gen}
						<li class="history-item">
							<div class="history-info">
								<p class="history-subject">{gen.title || gen.subject}</p>
								<div class="history-meta">
									<span class="status status-{gen.status}">{gen.status}</span>
									<span>{gen.subject}</span>
									<span>{gen.booklet_status}</span>
									<span>{gen.document_section_count}/{gen.section_count} sections</span>
								</div>
								{#if gen.status === 'failed'}
									<p class="failure-copy">
										{friendlyGenerationErrorMessage(null, null, null)}
									</p>
								{/if}
							</div>
							<div class="history-actions">
								<a href={v3OpenRoute(gen.id)} class="view-link">Open</a>
								{#if gen.status === 'completed'}
									<button
										type="button"
										class="view-link action-link"
										disabled={openingBuilderId === gen.id}
										onclick={() => openGenerationInBuilder(gen.id, gen.title || gen.subject)}
									>
										{openingBuilderId === gen.id ? 'Opening...' : 'Edit in Builder'}
									</button>
								{/if}
							</div>
						</li>
					{/each}
				</ul>
			</section>
		{/if}
	{/if}
</div>

<style>
	.dashboard {
		display: grid;
		gap: 1.5rem;
	}

	.welcome-section,
	.generate-section,
	.history-section {
		border: 1px solid rgba(36, 52, 63, 0.12);
		border-radius: 26px;
		background: rgba(255, 251, 244, 0.84);
		box-shadow: 0 18px 50px rgba(72, 52, 23, 0.08);
		padding: 1.35rem;
	}

	.eyebrow {
		margin: 0 0 0.3rem 0;
		font-size: 0.78rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: #6b7c88;
	}

	.welcome-section h1,
	.generate-section h2,
	.history-section h2 {
		margin: 0;
	}

	.subtitle,
	.generate-section > p {
		color: #655c52;
		max-width: 60ch;
	}

	.studio-link,
	.ghost-link {
		border-radius: 999px;
		border: 1px solid rgba(36, 52, 63, 0.18);
		background: rgba(36, 52, 63, 0.05);
		color: #24343f;
		padding: 0.45rem 0.85rem;
		cursor: pointer;
	}

	.studio-entry {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.9rem 1rem;
		border-radius: 18px;
		background: rgba(255, 255, 255, 0.58);
		border: 1px solid rgba(36, 52, 63, 0.08);
		margin: 1rem 0;
	}

	.studio-entry-prominent {
		align-items: stretch;
		padding: 1.1rem 1.15rem;
	}

	.studio-entry-copy {
		display: grid;
		gap: 0.45rem;
		color: #655c52;
	}

	.studio-entry-copy p,
	.studio-entry-copy h3 {
		margin: 0;
	}

	.studio-kicker {
		font-size: 0.76rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: #6b7c88;
	}

	.studio-features {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem;
		margin-top: 0.2rem;
	}

	.studio-features span {
		border-radius: 999px;
		background: rgba(29, 158, 117, 0.1);
		padding: 0.22rem 0.65rem;
		font-size: 0.78rem;
		color: #0b6a52;
	}

	.studio-entry-actions {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		justify-content: center;
		min-width: 12rem;
	}

	.studio-link {
		text-decoration: none;
		white-space: nowrap;
		text-align: center;
	}

	.ghost-link {
		background: rgba(255, 255, 255, 0.7);
	}

	.history-list {
		list-style: none;
		padding: 0;
		margin: 1rem 0 0 0;
		display: grid;
		gap: 0.85rem;
	}

	.history-item {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		padding: 1rem;
		border-radius: 18px;
		background: rgba(255, 255, 255, 0.72);
		border: 1px solid rgba(36, 52, 63, 0.1);
	}

	.history-subject {
		margin: 0;
		font-size: 1rem;
		font-weight: 700;
	}

	.history-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.55rem;
		margin-top: 0.5rem;
		color: #5e554b;
		font-size: 0.9rem;
	}

	.status {
		padding: 0.2rem 0.55rem;
		border-radius: 999px;
		font-size: 0.76rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.status-pending,
	.status-running {
		background: rgba(54, 101, 130, 0.12);
		color: #28516b;
	}

	.status-completed,
	.status-complete {
		background: rgba(61, 120, 73, 0.13);
		color: #276135;
	}

	.status-failed {
		background: rgba(148, 66, 46, 0.12);
		color: #8d3a26;
	}

	.view-link {
		color: #24436a;
		font-weight: 600;
		text-decoration: none;
	}

	.action-link {
		border: none;
		background: none;
		cursor: pointer;
		color: #1d6a52;
		font: inherit;
		padding: 0;
	}

	.action-link:disabled {
		cursor: progress;
		opacity: 0.68;
	}

	.history-actions {
		display: flex;
		gap: 0.6rem;
		align-items: center;
	}

	.failure-copy {
		margin: 0.5rem 0 0 0;
		color: #864635;
		font-size: 0.9rem;
	}

	@media (max-width: 720px) {
		.studio-entry,
		.history-item {
			display: grid;
		}

		.studio-entry-actions {
			min-width: auto;
		}
	}
</style>
