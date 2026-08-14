<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { fromStore } from 'svelte/store';
	import ProfileSetup from '$lib/components/ProfileSetup.svelte';
	import { fetchCurrentUser } from '$lib/api/auth';
	import { isApiError } from '$lib/api/errors';
	import { getOnboardingRoute, isOnboardingEditMode, resolveOnboardingGuard } from '$lib/auth/routing';
	import { createProfile, getProfile, updateProfile } from '$lib/api/profile';
	import { authUser, logout, updateUser } from '$lib/stores/auth';
	import type { TeacherProfile, TeacherProfileUpsertRequest } from '$lib/types';

	let saving = $state(false);
	let errorMessage: string | null = $state(null);
	let loadingProfile = $state(false);
	let initialData: TeacherProfileUpsertRequest | null = $state(null);
	let recoveringExistingProfile = $state(false);

	const user = fromStore(authUser);
	const editMode = $derived(isOnboardingEditMode(page.url));

	function toProfileFormData(profile: TeacherProfile): TeacherProfileUpsertRequest {
		return {
			teacher_role: profile.teacher_role,
			subjects: profile.subjects,
			default_grade_band: profile.default_grade_band,
			default_audience_description: profile.default_audience_description,
			curriculum_framework: profile.curriculum_framework,
			classroom_context: profile.classroom_context,
			planning_goals: profile.planning_goals,
			school_or_org_name: profile.school_or_org_name,
			delivery_preferences: profile.delivery_preferences
		};
	}

	onMount(async () => {
		const redirectTo = resolveOnboardingGuard(user.current, editMode);
		if (redirectTo) {
			goto(redirectTo, { replaceState: true });
			return;
		}

		if (!editMode && user.current?.has_profile) {
			return;
		}

		loadingProfile = true;
		try {
			const profile = await getProfile();
			initialData = toProfileFormData(profile);
			recoveringExistingProfile = !editMode;

			if (!user.current?.has_profile && user.current) {
				updateUser({ ...user.current, has_profile: true });
			}
		} catch (err) {
			if (isApiError(err) && err.status === 401) {
				logout();
				goto('/login', { replaceState: true });
				return;
			}

			if (isApiError(err) && err.status === 404) {
				if (editMode) {
					goto(getOnboardingRoute(), { replaceState: true });
				}
				return;
			}

			errorMessage = err instanceof Error ? err.message : 'Failed to load your profile.';
		} finally {
			loadingProfile = false;
		}
	});

	async function handleSubmit(data: TeacherProfileUpsertRequest) {
		saving = true;
		errorMessage = null;

		try {
			if (editMode || recoveringExistingProfile) {
				await updateProfile(data);
			} else {
				try {
					await createProfile(data);
				} catch (err) {
					if (isApiError(err) && err.status === 409) {
						recoveringExistingProfile = true;
						await updateProfile(data);
					} else {
						throw err;
					}
				}
			}

			try {
				const refreshedUser = await fetchCurrentUser();
				updateUser(refreshedUser);
			} catch {
				if (user.current) {
					updateUser({ ...user.current, has_profile: true });
				}
			}

			goto('/units', { replaceState: true });
		} catch (err) {
			if (isApiError(err) && err.status === 401) {
				logout();
				goto('/login', { replaceState: true });
				return;
			}

			errorMessage = err instanceof Error ? err.message : 'Failed to save profile.';
		} finally {
			saving = false;
		}
	}
</script>

<div class="onboarding">
	<h1>{editMode || recoveringExistingProfile ? 'Update your teacher setup' : `Welcome${user.current?.name ? `, ${user.current.name}` : ''}!`}</h1>
	<p>
		{#if editMode || recoveringExistingProfile}
			Refresh your saved teaching defaults so Studio can start closer to how you actually work.
		{:else}
			Let's capture your teaching context, classroom defaults, and lesson preferences so the product can personalise your workspace.
		{/if}
	</p>

	{#if recoveringExistingProfile && !editMode}
		<p class="recovery-note">
			We found an existing profile for this account and switched into recovery mode so you can resave it safely.
		</p>
	{/if}

	{#if loadingProfile}
		<p>Loading your profile...</p>
	{:else}
		<ProfileSetup
			onsubmit={handleSubmit}
			disabled={saving}
			initialData={initialData}
			submitLabel={editMode || recoveringExistingProfile ? 'Save Profile' : 'Complete Setup'}
		/>
	{/if}

	{#if errorMessage}
		<p class="error">{errorMessage}</p>
	{/if}
</div>

<style>
	.onboarding {
		max-width: 720px;
	}

	h1 {
		margin: 0 0 0.5rem;
		font-size: clamp(2rem, 4vw, 2.65rem);
		line-height: 1.05;
		letter-spacing: -0.02em;
		color: #1f2b34;
	}

	p {
		max-width: 60ch;
		color: #5c554c;
		margin: 0 0 1.75rem;
		font-size: 1.02rem;
		line-height: 1.65;
	}

	.error {
		color: #8e3b32;
		margin-top: 1rem;
		padding: 0.9rem 1rem;
		border-radius: 12px;
		background: rgba(255, 242, 238, 0.88);
		border: 1px solid rgba(180, 92, 74, 0.18);
	}

	.recovery-note {
		color: #70541d;
		margin-top: -0.75rem;
		padding: 0.8rem 0.95rem;
		border-radius: 12px;
		background: rgba(255, 247, 225, 0.9);
		border: 1px solid rgba(183, 138, 38, 0.2);
	}
</style>
