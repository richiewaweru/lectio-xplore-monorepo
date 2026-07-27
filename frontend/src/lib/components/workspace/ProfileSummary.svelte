<script lang="ts">
	import type { TeacherProfile } from '$lib/types';

	interface Props {
		profile: TeacherProfile;
		onEdit: () => void;
	}

	let { profile, onEdit }: Props = $props();
</script>

<section class="profile-summary">
	<h2>Teacher Setup</h2>
	<div class="profile-grid">
		<div class="profile-item">
			<span class="label">Teacher Role</span>
			<span class="value">{profile.teacher_role.replace('_', ' ')}</span>
		</div>
		<div class="profile-item">
			<span class="label">Default Grade Band</span>
			<span class="value">{profile.default_grade_band.replace('_', ' ')}</span>
		</div>
		<div class="profile-item">
			<span class="label">Tone</span>
			<span class="value">{profile.delivery_preferences.tone.replace('_', ' ')}</span>
		</div>
		<div class="profile-item">
			<span class="label">Brevity</span>
			<span class="value">{profile.delivery_preferences.brevity.replace('_', ' ')}</span>
		</div>
		{#if profile.subjects.length > 0}
			<div class="profile-item wide">
				<span class="label">Subjects</span>
				<span class="value">{profile.subjects.join(', ')}</span>
			</div>
		{/if}
		{#if profile.default_audience_description}
			<div class="profile-item wide">
				<span class="label">Default Audience</span>
				<span class="value">{profile.default_audience_description}</span>
			</div>
		{/if}
		{#if profile.curriculum_framework}
			<div class="profile-item wide">
				<span class="label">Curriculum</span>
				<span class="value">{profile.curriculum_framework}</span>
			</div>
		{/if}
		{#if profile.classroom_context}
			<div class="profile-item wide">
				<span class="label">Classroom Context</span>
				<span class="value">{profile.classroom_context}</span>
			</div>
		{/if}
		{#if profile.planning_goals}
			<div class="profile-item wide">
				<span class="label">Planning Goals</span>
				<span class="value">{profile.planning_goals}</span>
			</div>
		{/if}
	</div>
	<button class="edit-profile-btn" onclick={onEdit}>Edit Profile</button>
</section>

<style>
	.profile-summary {
		border: 1px solid rgba(36, 52, 63, 0.12);
		border-radius: 26px;
		background: rgba(255, 251, 244, 0.84);
		box-shadow: 0 18px 50px rgba(72, 52, 23, 0.08);
		padding: 1.35rem;
	}

	h2 {
		margin: 0;
	}

	.profile-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
		gap: 0.8rem;
		margin: 1rem 0;
	}

	.profile-item {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.profile-item.wide {
		grid-column: 1 / -1;
	}

	.label {
		color: #6f6b63;
		font-size: 0.78rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
	}

	.value {
		color: #1f1c18;
		text-transform: capitalize;
	}

	.edit-profile-btn {
		border: 1px solid rgba(36, 52, 63, 0.18);
		border-radius: 999px;
		background: rgba(36, 52, 63, 0.05);
		color: #24343f;
		cursor: pointer;
		padding: 0.45rem 0.85rem;
	}
</style>
