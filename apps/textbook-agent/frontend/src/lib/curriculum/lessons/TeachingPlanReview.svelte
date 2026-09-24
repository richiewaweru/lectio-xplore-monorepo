<script lang="ts">
	import type { LessonApproachView, TeachingPlanIdentityView, TeachingPlanView } from './teaching-plan-review';
	let {
		plan,
		review,
		identity
	}: {
		plan: TeachingPlanView;
		review?: LessonApproachView['teaching_review'];
		identity?: TeachingPlanIdentityView;
	} = $props();
</script>

<div class="review-grid">
	<section aria-label="Teaching plan content" class="plan-content">
		<h3>Teaching plan content</h3>
		{#if plan.contract_version === 2}
			{#if plan.learner_title}<h4 class="learner-title">{plan.learner_title}</h4>{/if}
			{#if plan.starting_state?.length}
				<p class="label">Starting state</p>
				<ul>{#each plan.starting_state as state}<li>{state}</li>{/each}</ul>
			{/if}
			{#if plan.target_state?.length}
				<p class="label">Target state</p>
				<ul>{#each plan.target_state as state}<li>{state}</li>{/each}</ul>
			{/if}
		{/if}
		<p class="label">Pedagogical arc</p>
		<p>{plan.arc}</p>
		{#if plan.anchor_usage?.length}
			<p class="label">Anchor usage</p>
			<ul>{#each plan.anchor_usage as anchor}<li><strong>{anchor.slot_id}:</strong> {anchor.usage}</li>{/each}</ul>
		{/if}
		{#if plan.misconception_focus_ids?.length}
			<p class="label">Misconceptions to address</p>
			<ul>{#each plan.misconception_focus_ids as misconception}<li>{misconception}</li>{/each}</ul>
		{/if}
		{#each plan.sections ?? [] as section (section.slot_id)}
			<article>
				{#if plan.contract_version === 2}
					<h4>{section.display_title || section.slot_id}</h4>
					<p class="label">Section slot</p>
					<p>{section.slot_id}</p>
					{#if section.entry_state?.length}
						<p class="label">Entry state</p>
						<ul>{#each section.entry_state as state}<li>{state}</li>{/each}</ul>
					{/if}
					{#if section.must_establish?.length}
						<p class="label">Must establish</p>
						<ul>{#each section.must_establish as item}<li>{item}</li>{/each}</ul>
					{/if}
					{#if section.avoid_repeating?.length}
						<p class="label">Avoid repeating</p>
						<ul>{#each section.avoid_repeating as item}<li>{item}</li>{/each}</ul>
					{/if}
					<p class="label">Bridge from previous</p>
					<p>{section.bridge_from_previous || 'First section; no prior bridge.'}</p>
					{#if section.exit_state?.length}
						<p class="label">Exit state</p>
						<ul>{#each section.exit_state as state}<li>{state}</li>{/each}</ul>
					{/if}
				{:else}
					<h4>{section.slot_id}</h4>
				{/if}
				{#if section.specific_purpose}<p>{section.specific_purpose}</p>{/if}
				{#if section.transition}<p><strong>Transition:</strong> {section.transition}</p>{/if}
				{#each section.blocks ?? [] as block (block.id)}
					<div class="block">
						<p class="label">{block.intent} · {block.id}</p>
					<p>{block.brief}</p>
					<p><strong>Evidence:</strong> {block.evidence}</p>
					{#if block.evidence_refs?.length}<p><strong>Evidence sources:</strong> {block.evidence_refs.join(', ')}</p>{/if}
					{#if block.source_question_ids?.length}<p><strong>Source questions:</strong> {block.source_question_ids.join(', ')}</p>{/if}
					{#if block.task_mode && block.task_mode !== 'none'}<p><strong>Task mode:</strong> {block.task_mode}</p>{/if}
					{#if block.sourcebook_needs?.length}<p><strong>Sourcebook needs:</strong> {block.sourcebook_needs.join(', ')}</p>{/if}
					{#if block.sourcebook_refs?.length}<p><strong>Sourcebook references:</strong> {block.sourcebook_refs.join(', ')}</p>{/if}
					{#if block.stimulus_dependencies?.length}<p><strong>Stimulus dependencies:</strong> {block.stimulus_dependencies.join(', ')}</p>{/if}
					{#if block.learner_action}
						<div class="learner-action">
							<p class="label">Learner action · {block.learner_action.action}</p>
							<p>{block.learner_action.target} — {block.learner_action.purpose}</p>
							<p><strong>Expected evidence:</strong> {block.learner_action.expected_evidence} · {block.learner_action.difficulty}</p>
						</div>
					{/if}
					{#if block.departure_reason}<p class="notice">Departure: {block.departure_reason}</p>{/if}
				</div>
				{/each}
			</article>
		{/each}
	</section>
	<aside aria-label="Review metadata" class="review-meta">
		<h3>Review</h3>
		<p>Status: {review?.status ?? 'unknown'}</p>
		<p>Revision: {review?.revision ?? 'unknown'}</p>
		{#if String(review?.status ?? '').toLowerCase() === 'approved' && identity?.approved_hash_verified && identity.approved_content_hash}
			<p>Verified approved revision: {identity.approved_revision}</p>
			<p>Approved content hash: {identity.approved_content_hash}</p>
		{:else if String(review?.status ?? '').toLowerCase() === 'pending' && identity?.pending_hash_verified && identity.pending_content_hash}
			<p>Verified pending content hash: {identity.pending_content_hash}</p>
		{/if}
	</aside>
</div>

<style>
	.review-grid { display: grid; gap: 1rem; }
	.plan-content, .review-meta { border: 1px solid var(--color-border, #d5d9df); border-radius: .75rem; padding: 1rem; }
	.plan-content h3, .review-meta h3 { margin: 0 0 .75rem; font-size: 1rem; }
	.plan-content article { margin-top: 1rem; border-top: 1px solid var(--color-border, #d5d9df); padding-top: .75rem; }
	.plan-content h4 { margin: 0 0 .4rem; }
	.plan-content .learner-title { font-size: 1.2rem; }
	.plan-content p { margin: .35rem 0; }
	.plan-content ul { margin: .35rem 0; padding-left: 1.25rem; }
	.label { font-size: .8rem; font-weight: 650; }
	.block { margin-top: .75rem; padding-top: .65rem; border-top: 1px dashed var(--color-border, #d5d9df); }
	.learner-action { margin-top: .5rem; padding: .5rem; background: color-mix(in srgb, var(--color-primary, #2672bd) 8%, transparent); border-radius: .4rem; }
	.notice { color: #9a5700; }
</style>
