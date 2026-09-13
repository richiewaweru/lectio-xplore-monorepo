<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { page } from '$app/state';
	import TeachingSchedulePanel from '$lib/curriculum/units/components/TeachingSchedulePanel.svelte';
	import UnitGroupsPanel from '$lib/curriculum/units/components/UnitGroupsPanel.svelte';
	import LessonShapePanel from '$lib/curriculum/units/components/LessonShapePanel.svelte';
	import LessonVersionsPanel from '$lib/curriculum/units/components/LessonVersionsPanel.svelte';
	import LessonResultsPanel from '$lib/curriculum/units/components/LessonResultsPanel.svelte';
	import ResourceComposerPanel from '$lib/curriculum/units/components/ResourceComposerPanel.svelte';
	import {
		PATH_INDEPENDENCE_COPY,
		generatePathLabel,
		openPathLabel,
		pathHasRealization
	} from '$lib/curriculum/units/path-generation';
	import { createUnitWorkspace } from '$lib/curriculum/units/unit-workspace.svelte';
	import { createLearnPathJobState } from '$lib/learn/jobs/path-job-state';
	import { createPrintPathJobState } from '$lib/print/jobs/path-job-state';
	import type { LessonMode } from '$lib/types/units';

	const printJob = createPrintPathJobState();
	const learnJob = createLearnPathJobState();
	const ws = createUnitWorkspace(() => page.params.id ?? '', { printJob, learnJob });
	const debugMode = import.meta.env.DEV;
	const unitId = $derived(page.params.id ?? '');

	onMount(() => void ws.load());
	onDestroy(() => ws.dispose());
</script>

<svelte:head><title>{ws.unit ? `${ws.unit.title} · Units` : 'Unit · Lectio'}</title></svelte:head>

<div class="unit-page">
	{#if ws.loading && !ws.unit}
		<p class="loading" role="status">Loading unit…</p>
	{:else if ws.unit}
		<header class="unit-head">
			<div><a href="/units" class="back">← Units</a><p class="eyebrow">{ws.unit.subject} · {ws.unit.grade_level}</p><h1>{ws.unit.title}</h1><p>{ws.unit.destination_objective}</p></div>
			<div class="head-actions">
				{#if ws.path}<span class:approved={ws.path.status === 'approved'}>{ws.path.status === 'approved' ? 'Locked in' : 'Draft'}</span>{/if}
				<button class="secondary" type="button" disabled={ws.laneBusy('plan') || !ws.actionAllowed('plan')} onclick={() => ws.planOrReplan(Boolean(ws.path))}>{ws.laneBusy('plan') ? 'Planning…' : ws.path ? 'Replan the lessons' : 'Plan the lessons'}</button>
			</div>
		</header>

		{#if ws.error}<p class="error" role="alert">{ws.error}</p>{/if}
		{#if ws.conflict}
			<div class="conflict" role="alertdialog" aria-labelledby="conflict-title">
				<p class="eyebrow">Revision conflict</p>
				<h2 id="conflict-title">Your edits were kept</h2>
				<p>{ws.conflict.message}</p>
				<p class="hint">Another tab or session saved a newer revision. Reload to take the server version, or keep editing your local draft.</p>
				<div class="conflict-actions">
					<button type="button" class="secondary" onclick={() => ws.resolveEditConflict('keep_editing')}>Keep editing</button>
					<button type="button" class="primary" onclick={() => ws.resolveEditConflict('reload_server')}>Reload from server</button>
				</div>
			</div>
		{/if}
		{#if ws.dirty}
			<p class="dirty-hint" role="status">Unsaved lesson edits — progress updates will not overwrite them.</p>
		{/if}

		{#if !ws.path}
			<section class="empty">
				{#if ws.planningFailed}
					<p class="eyebrow">Planning did not finish</p>
					<h2>This unit is saved as a draft</h2>
					<p>Lesson planning did not complete. Nothing else was corrupted — try planning again on this same unit.</p>
					<button class="primary" type="button" disabled={ws.laneBusy('plan')} onclick={() => ws.planOrReplan(false)}>{ws.laneBusy('plan') ? 'Planning your lessons…' : 'Try planning again'}</button>
				{:else}
					<p class="eyebrow">Destination saved</p>
					<h2>Build your lessons</h2>
					<p>This turns your destination into a numbered list of lessons.</p>
					<button class="primary" type="button" disabled={ws.laneBusy('plan')} onclick={() => ws.planOrReplan(false)}>{ws.laneBusy('plan') ? 'Planning your lessons…' : 'Plan the lessons'}</button>
				{/if}
			</section>
		{:else}
			<nav class="view-tabs" aria-label="Unit workspace views">
				<button type="button" class:active={ws.activeView === 'path'} aria-current={ws.activeView === 'path' ? 'page' : undefined} onclick={() => ws.openTab('path')}>Lessons</button>
				<button type="button" class:active={ws.activeView === 'schedule'} aria-current={ws.activeView === 'schedule' ? 'page' : undefined} onclick={() => ws.openTab('schedule')}>Schedule</button>
				<button type="button" class:active={ws.activeView === 'groups'} aria-current={ws.activeView === 'groups' ? 'page' : undefined} onclick={() => ws.openTab('groups')}>Groups</button>
				<button type="button" class:active={ws.activeView === 'resources'} aria-current={ws.activeView === 'resources' ? 'page' : undefined} onclick={() => ws.openTab('resources')}>Resources</button>
				<button type="button" class:active={ws.activeView === 'results'} aria-current={ws.activeView === 'results' ? 'page' : undefined} onclick={() => ws.openTab('results')}>Results</button>
				<button type="button" class:active={ws.activeView === 'history'} aria-current={ws.activeView === 'history' ? 'page' : undefined} onclick={() => ws.openTab('history')}>History</button>
			</nav>
			{#if ws.tabError && ws.activeView !== 'path'}
				<p class="error" role="alert">{ws.tabError}</p>
			{/if}
			{#if ws.activeView === 'path'}
			{#if ws.mergeSuggestions.some((row) => !ws.dismissedSuggestions.includes(ws.suggestionKey(row)))}
				<section class="suggestions" aria-label="Lesson suggestions">
					<p class="eyebrow">Suggestions</p>
					<ul>
						{#each ws.mergeSuggestions as row (ws.suggestionKey(row))}
							{#if !ws.dismissedSuggestions.includes(ws.suggestionKey(row))}
								<li>
									<p>{row.reason}</p>
									<div class="suggestion-actions">
										<button type="button" disabled={ws.laneBusy('merge')} onclick={() => ws.openMergeReview(row)}>Review merge</button>
										<button type="button" class="ghost" disabled={ws.laneBusy('merge')} onclick={() => { ws.dismissedSuggestions = [...ws.dismissedSuggestions, ws.suggestionKey(row)]; }}>Dismiss</button>
									</div>
								</li>
							{/if}
						{/each}
					</ul>
				</section>
			{/if}
			{#if ws.mergeDraft}
				<section class="merge-editor" aria-label="Review merge">
					<p class="eyebrow">Merge {ws.mergeDraft.lessonALabel} + {ws.mergeDraft.lessonBLabel}</p>
					<label><span>Title</span><input bind:value={ws.mergeDraft.title} /></label>
					<div class="merge-source-objectives">
						<p><strong>{ws.mergeDraft.lessonALabel}:</strong> {ws.mergeDraft.objectiveA}</p>
						<p><strong>{ws.mergeDraft.lessonBLabel}:</strong> {ws.mergeDraft.objectiveB}</p>
					</div>
					<label>
						<span>Objective</span>
						<textarea bind:value={ws.mergeDraft.objective} placeholder="Write one capability that genuinely covers both lessons."></textarea>
						<small>Write one capability that genuinely covers both lessons.</small>
					</label>
					<label><span>Must establish <small>one per line</small></span><textarea bind:value={ws.mergeDraft.mustEstablish}></textarea></label>
					<label>
						<span>Knowledge type</span>
						<select bind:value={ws.mergeDraft.knowledgeType}>
							<option value="">Select a type</option>
							<option value="factual">Factual</option>
							<option value="conceptual">Conceptual</option>
							<option value="procedural">Procedural</option>
							<option value="evaluative">Evaluative</option>
						</select>
					</label>
					<div class="suggestion-actions">
						<button type="button" class="ghost" disabled={ws.laneBusy('merge')} onclick={() => ws.cancelMergeReview()}>Cancel</button>
						<button class="primary" type="button" disabled={ws.laneBusy('merge') || !ws.mergeDraftValid} onclick={() => ws.confirmMergeReview()}>Merge lessons</button>
					</div>
				</section>
			{/if}

			{#if ws.path.status !== 'approved'}
				<section class="lock-in-bar">
					<div>
						<p class="eyebrow">Ready to teach from?</p>
						<p>Locking it in freezes this lesson route so Print and Learn can be generated from it.</p>
					</div>
					<div class="lock-in">
						<button class="primary" type="button" disabled={ws.laneBusy('approve') || !ws.canLockIn || !ws.actionAllowed('approve')} onclick={() => ws.approvePath()}>{ws.laneBusy('approve') ? 'Locking it in…' : 'Looks good — lock it in'}</button>
					</div>
				</section>
			{/if}

			<div class="workspace">
				<aside class="path-list" aria-label="Your lessons">
					<p class="eyebrow">Your lessons</p>
					<ol>{#each ws.path.lessons as lesson, index (lesson.id)}<li class:active={lesson.id === ws.selectedId} class:skipped={lesson.skipped}><button type="button" onclick={() => ws.selectLesson(lesson)}><span>{index + 1}</span><span><strong>{lesson.title}</strong>{#if ws.dependencySentences(lesson).length}<small>{ws.dependencySentences(lesson).join(' · ')}</small>{:else if lesson.pack_id}<small>prepared</small>{/if}</span></button></li>{/each}</ol>
				</aside>

				{#if ws.selected}
					<main class="inspector">
						<div class="inspector-head"><div><p class="eyebrow">Lesson {ws.selected.position + 1}</p><h2>{ws.selected.title}</h2></div></div>

						<form class="editor" onsubmit={(e) => ws.saveLesson(e)}>
							<label><span>Title</span><input bind:value={ws.editTitle} required /></label>
							<label><span>What students will be able to do</span><textarea bind:value={ws.editObjective} required></textarea></label>
							<label><span>Must establish <small>one per line</small></span><textarea bind:value={ws.editMustEstablish} required></textarea></label>
							<button class="secondary" type="submit" disabled={ws.laneBusy('save') || !ws.actionAllowed('save')}>{ws.laneBusy('save') ? 'Saving…' : 'Save lesson changes'}</button>
						</form>

						<section class="dependencies"><div><p class="eyebrow">Before this lesson</p><h3>What earlier lessons it requires</h3></div>{#if ws.dependencySentences(ws.selected).length}<ul>{#each ws.dependencySentences(ws.selected) as sentence}<li>{sentence}</li>{/each}</ul>{:else}<p>Nothing — this can be the starting point.</p>{/if}</section>

						{#if debugMode}
							<section class="shape">
								{#if !ws.showShapeDebug}
									<button class="text-button" type="button" onclick={() => { ws.showShapeDebug = true; ws.shapeError = null; void ws.ensureShape(); }}>Show shape debug</button>
								{:else if ws.shape}
									<LessonShapePanel
										{unitId}
										path={ws.path}
										lesson={ws.selected}
										shape={ws.shape}
										lessonMode={ws.lessonMode}
										misconceptionCount={ws.misconceptionCount}
										{debugMode}
										onsettings={(mode: LessonMode, count: number) => ws.updateShapeSettings(mode, count)}
										onshape={(value) => (ws.shape = value)}
										onrevision={(revision: number) => ws.updateShapeRevision(revision)}
									/>
								{:else if ws.shapeError}
									<p class="error" role="alert">{ws.shapeError}</p>
									<button class="text-button" type="button" onclick={() => { ws.shapeError = null; void ws.ensureShape(); }}>Retry shape</button>
								{:else}
									<p>Loading this lesson's shape…</p>
								{/if}
							</section>
						{/if}

						<section class="prepare">
							<div>
								<p class="eyebrow">Preparation</p>
								<h3>{ws.preparation?.workflow_stage ?? 'Ready when you are'}</h3>
								<p>{PATH_INDEPENDENCE_COPY}</p>
								{#if ws.preparation?.stale}
									<p>This lesson changed since it was last written and needs to be made again.</p>
								{/if}
								{#if ws.runStatus}
									<p class="hint" role="status">
										Run {ws.runStatus.status}
										{#if ws.runStatus.completed_count != null && ws.runStatus.total_count != null}
											· {ws.runStatus.completed_count}/{ws.runStatus.total_count}
										{/if}
									</p>
								{/if}
							</div>
							{#if ws.preparation?.stale && ws.preparation?.can_regenerate}
								<form class="regenerate" onsubmit={(event) => { event.preventDefault(); void ws.regenerate(); }}>
									<label><span>What changed</span><input bind:value={ws.regenerationReason} minlength="3" maxlength="500" required /></label>
									<button class="primary" type="submit" disabled={ws.laneBusy('regenerate') || ws.regenerationReason.trim().length < 3 || !ws.actionAllowed('regenerate')}>{ws.laneBusy('regenerate') ? 'Making it again…' : 'Make it again'}</button>
								</form>
							{:else if ws.canStartFresh}
								<form class="regenerate" onsubmit={(event) => { event.preventDefault(); void ws.regenerate(); }}>
									<p>The previous generation cannot be retried. Start fresh to keep it as failure history and create a new generation.</p>
									<label><span>Why start fresh</span><input bind:value={ws.regenerationReason} minlength="3" maxlength="500" required /></label>
									<button class="primary" type="submit" disabled={ws.laneBusy('regenerate') || ws.regenerationReason.trim().length < 3}>{ws.laneBusy('regenerate') ? 'Starting fresh…' : 'Start fresh'}</button>
								</form>
							{:else if ws.preparation?.generation_id || (ws.preparation?.realizations?.length ?? 0) > 0}
								{@const prep = ws.preparation}
								<div class="ready-actions">
									{#if prep?.print_open_href}
										<a class="primary link" href={prep.print_open_href}>{openPathLabel('print')}</a>
									{:else if prep?.generation_id && pathHasRealization(prep, 'print')}
										<a class="primary link" href={`/studio/print/${encodeURIComponent(prep.generation_id)}`}>{openPathLabel('print')}</a>
									{:else if !pathHasRealization(prep, 'print')}
										<button class="primary" type="button" disabled={!ws.canGeneratePrint() || ws.laneBusy('print')} onclick={() => ws.prepare('print')}>{ws.laneBusy('print') ? 'Generating Print…' : generatePathLabel('print')}</button>
									{/if}
									{#if prep?.learn_open_href}
										<a class="secondary link" href={prep.learn_open_href}>{openPathLabel('learn')}</a>
									{:else if prep?.learn_output_id}
										<a class="secondary link" href={`/studio?generation_id=${encodeURIComponent(prep.learn_output_id)}`}>{openPathLabel('learn')}</a>
									{:else if !pathHasRealization(prep, 'learn')}
										<button class="secondary" type="button" disabled={!ws.canGenerateLearn() || ws.laneBusy('learn')} onclick={() => ws.prepare('learn')}>{ws.laneBusy('learn') ? 'Generating Learn…' : generatePathLabel('learn')}</button>
									{/if}
									{#if prep?.realizations?.some((row) => row.status === 'read_only')}
										<p class="hint">A legacy output is read-only — generate an explicit Print or Learn realization from the Teaching Plan.</p>
									{/if}
									<button class="secondary" type="button" onclick={() => { void ws.openTab('groups'); ws.showVersions = true; }}>Make versions for my groups</button>
									<button class="text-button" type="button" onclick={() => ws.ensurePreparationStatus()}>Refresh status</button>
									<button class="text-button" type="button" onclick={() => ws.reconnectSubscription()}>Reconnect progress</button>
								</div>
							{:else}
								<div class="ready-actions">
									<button class="primary" type="button" disabled={!ws.canGeneratePrint() || ws.laneBusy('print')} onclick={() => ws.prepare('print')}>{ws.laneBusy('print') ? 'Generating Print…' : generatePathLabel('print')}</button>
									<button class="secondary" type="button" disabled={!ws.canGenerateLearn() || ws.laneBusy('learn')} onclick={() => ws.prepare('learn')}>{ws.laneBusy('learn') ? 'Generating Learn…' : generatePathLabel('learn')}</button>
									<button class="text-button" type="button" onclick={() => ws.ensurePreparationStatus()}>Check preparation status</button>
								</div>
							{/if}
						</section>
					</main>
				{/if}
			</div>

			<section class="chat-edit" aria-label="Edit your lessons by chat">
				<p class="eyebrow">Edit your lessons</p>
				{#if ws.chatUnavailable}
					<p class="chat-disabled">Editing lessons by chat isn't available yet — use the lesson tools above for now.</p>
				{:else}
					<form onsubmit={(e) => ws.sendChatEdit(e)}>
						<input bind:value={ws.chatMessage} placeholder="e.g. Combine lessons 2 and 3, or add something about fractions" disabled={ws.laneBusy('chat')} />
						<button class="primary" type="submit" disabled={ws.laneBusy('chat') || ws.chatMessage.trim().length < 2}>{ws.laneBusy('chat') ? 'Updating…' : 'Send'}</button>
					</form>
					{#if ws.chatNote}<p class="chat-note">{ws.chatNote}</p>{/if}
				{/if}
			</section>
			{:else if ws.activeView === 'schedule'}
				{#if ws.schedule}
					<TeachingSchedulePanel {unitId} path={ws.path} schedule={ws.schedule} onsaved={(saved) => (ws.schedule = saved)} />
				{:else if !ws.tabError}
					<p class="loading" role="status">Loading schedule…</p>
				{/if}
			{:else if ws.activeView === 'groups'}
				{#if ws.groups}
					<UnitGroupsPanel {unitId} groups={ws.groups} onsaved={(saved) => { ws.groups = saved; ws.selectedGroupIds = saved.groups.map((group) => group.id); }} />
				{:else if !ws.tabError}
					<p class="loading" role="status">Loading groups…</p>
				{/if}
			{:else if ws.activeView === 'results'}
				{#if ws.groups}
					<LessonResultsPanel {unitId} path={ws.path} lessons={ws.path.lessons} groups={ws.groups} />
				{:else if !ws.tabError}
					<p class="loading" role="status">Loading results…</p>
				{/if}
			{:else if ws.activeView === 'resources'}
				{#if ws.groups && ws.schedule}
					<ResourceComposerPanel {unitId} path={ws.path} lessons={ws.path.lessons} groups={ws.groups} schedule={ws.schedule} compositions={ws.compositions} oncreated={(created) => (ws.compositions = [created, ...ws.compositions])} />
				{:else if !ws.tabError}
					<p class="loading" role="status">Loading resources…</p>
				{/if}
			{:else if ws.activeView === 'history'}
				<section class="history-panel">
					<div class="section-head"><div><p class="eyebrow">Lesson history</p><h2>Recoverable versions</h2></div><p>Structural edits create a new draft. Older routes remain available.</p></div>
					{#if ws.historyLoaded}
						<div class="history-list">{#each ws.history as version}<article class:current={version.id === ws.path.id}><div><strong>v{version.version}</strong><span>{version.status}</span><small>{version.generated_by}</small></div><div class="history-actions"><button type="button" class="text-button" onclick={() => ws.viewVersion(version)}>Inspect</button>{#if version.id !== ws.path.id}<button type="button" class="text-button" onclick={() => ws.confirmRestore(version)}>Restore</button>{/if}</div></article>{/each}</div>
						{#if ws.viewedVersion}<div class="history-preview"><div><strong>v{ws.viewedVersion.version}</strong><span>{ws.viewedVersion.status} · {ws.viewedVersion.lessons.length} lessons</span></div><ol>{#each ws.viewedVersion.lessons as lesson}<li>{lesson.title}</li>{/each}</ol><button type="button" class="text-button" onclick={() => (ws.viewedVersion = null)}>Close preview</button></div>{/if}
					{:else if !ws.tabError}
						<p class="loading" role="status">Loading history…</p>
					{/if}
				</section>
			{/if}
		{/if}
	{/if}
</div>

{#if ws.showVersions && ws.groups}
	<LessonVersionsPanel
		{unitId}
		groups={ws.groups}
		onsaved={(saved) => { ws.groups = saved; ws.selectedGroupIds = saved.groups.map((group) => group.id); }}
		onclose={() => (ws.showVersions = false)}
	/>
{/if}

{#if ws.pendingAction}
	<div class="confirm-backdrop" role="presentation">
		<div class="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
			<p class="eyebrow">Confirm structural change</p><h2 id="confirm-title">{ws.pendingAction.label}</h2><p>{ws.pendingAction.description}</p>
			{#if ws.pendingAction.label.startsWith('Restore')}<label><span>Recovery reason</span><input bind:value={ws.restoreReason} minlength="3" required /></label>{/if}
			<div><button type="button" class="secondary" onclick={() => (ws.pendingAction = null)}>Cancel</button><button type="button" class="primary" disabled={ws.laneBusy('restore') || (ws.pendingAction.label.startsWith('Restore') && ws.restoreReason.trim().length < 3)} onclick={() => ws.runPendingAction()}>Confirm</button></div>
		</div>
	</div>
{/if}

<style>
	.unit-page { min-height: calc(100vh - 58px); padding: 38px 28px 80px; }
	.unit-head, .view-tabs, .lock-in-bar, .history-panel, .workspace, .chat-edit, .empty, .error, .loading, .conflict, .dirty-hint { max-width: 1180px; margin-inline: auto; }
	.unit-head { display: flex; align-items: end; justify-content: space-between; gap: 24px; margin-bottom: 28px; }
	.back { display: inline-block; margin-bottom: 18px; color: var(--accent); font-size: 13px; font-weight: 600; text-decoration: none; }
	.eyebrow { margin: 0 0 6px; color: var(--ink-3); font: 500 10px 'IBM Plex Mono', monospace; letter-spacing: .1em; text-transform: uppercase; }
	h1 { margin: 0; font: 500 36px/1.1 Fraunces, Georgia, serif; letter-spacing: -.03em; }
	.unit-head p:last-child { max-width: 720px; margin: 9px 0 0; color: var(--ink-2); font-size: 14px; line-height: 1.5; }
	.head-actions { display: flex; align-items: center; gap: 10px; }
	.head-actions > span { border-radius: 999px; background: var(--amber-soft); color: var(--amber); font: 500 10px 'IBM Plex Mono', monospace; padding: 6px 9px; text-transform: uppercase; }
	.head-actions > span.approved { background: var(--accent-soft); color: var(--accent); }
	button, input, textarea, select { font: inherit; }
	.primary, .secondary, .text-button { cursor: pointer; }
	.primary, .secondary { border-radius: 7px; font-size: 13px; font-weight: 600; padding: 9px 13px; }
	.primary { border: 1px solid var(--accent); background: var(--accent); color: white; }
	.primary.link, .secondary.link { display: inline-block; text-decoration: none; }
	.secondary { border: 1px solid var(--rule); background: var(--surface); color: var(--ink); }
	button:disabled { cursor: not-allowed; opacity: .45; }
	.view-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--rule); margin-bottom: 22px; }
	.view-tabs button { border: 0; border-bottom: 2px solid transparent; background: transparent; color: var(--ink-3); cursor: pointer; padding: 10px 13px; font-size: 12px; font-weight: 600; }
	.view-tabs button.active { border-bottom-color: var(--accent); color: var(--accent); }
	.lock-in-bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); margin-bottom: 18px; padding: 16px 18px; }
	.suggestions { max-width: 1180px; margin: 0 auto 18px; border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); padding: 16px 18px; }
	.suggestions ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }
	.suggestions li { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
	.suggestions p { margin: 0; color: var(--ink-2); font-size: 13px; }
	.suggestion-actions { display: flex; gap: 8px; flex-shrink: 0; }
	.suggestion-actions .ghost { background: transparent; border: 1px solid var(--rule); color: var(--ink-2); }
	.merge-editor { max-width: 1180px; margin: 0 auto 18px; display: grid; gap: 12px; border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); padding: 16px 18px; }
	.merge-editor label { display: grid; gap: 6px; }
	.merge-editor input, .merge-editor textarea, .merge-editor select { width: 100%; border: 1px solid var(--rule); border-radius: 7px; background: var(--paper); color: var(--ink); padding: 9px 11px; }
	.merge-editor textarea { min-height: 72px; resize: vertical; }
	.merge-editor small { color: var(--ink-3); font-size: 12px; }
	.merge-source-objectives { display: grid; gap: 6px; color: var(--ink-2); font-size: 13px; }
	.merge-source-objectives p { margin: 0; }
	.lock-in-bar p { margin: 0; color: var(--ink-2); font-size: 13px; }
	.lock-in { display: grid; justify-items: end; gap: 6px; }
	.history-panel { border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); margin-bottom: 22px; padding: 18px; }
	.history-panel .section-head > p { max-width: 430px; margin: 0; color: var(--ink-3); font-size: 11px; text-align: right; }
	.history-list { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 13px; }
	.history-list article { display: flex; align-items: center; gap: 14px; border: 1px solid var(--rule); border-radius: 7px; padding: 8px 10px; }
	.history-list article.current { border-color: var(--accent); background: var(--accent-soft); }
	.history-list article > div:first-child { display: grid; grid-template-columns: auto auto; column-gap: 6px; align-items: baseline; }
	.history-list article span, .history-list article small { color: var(--ink-3); font-size: 9px; text-transform: uppercase; }
	.history-list article small { grid-column: 1 / -1; margin-top: 2px; text-transform: none; }
	.history-actions { display: flex; gap: 4px; }
	.history-preview { display: grid; gap: 10px; border-top: 1px solid var(--rule); margin-top: 15px; padding-top: 15px; }
	.history-preview > div { display: flex; gap: 8px; align-items: baseline; }
	.history-preview span { color: var(--ink-3); font-size: 11px; }
	.history-preview ol { display: flex; flex-wrap: wrap; gap: 5px 20px; margin: 0; padding-left: 20px; color: var(--ink-2); font-size: 11px; }
	.history-preview button { justify-self: start; }
	.workspace { display: grid; grid-template-columns: 300px minmax(0, 1fr); align-items: start; gap: 22px; }
	.path-list { position: sticky; top: 80px; border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); padding: 15px; }
	.path-list ol { display: grid; gap: 3px; margin: 0; padding: 0; list-style: none; }
	.path-list li button { display: grid; grid-template-columns: 24px minmax(0, 1fr); gap: 7px; width: 100%; border: 0; border-radius: 7px; background: transparent; color: var(--ink); padding: 9px; text-align: left; }
	.path-list li button > span:first-child { display: grid; place-items: center; width: 20px; height: 20px; border-radius: 50%; background: var(--paper); color: var(--ink-3); font: 500 10px 'IBM Plex Mono', monospace; }
	.path-list li button strong, .path-list li button small { display: block; }
	.path-list li button strong { font-size: 13px; }
	.path-list li button small { margin-top: 3px; color: var(--ink-3); font-size: 10px; }
	.path-list li.active button { background: var(--accent-soft); color: var(--accent); }
	.path-list li.skipped { opacity: .5; text-decoration: line-through; }
	.inspector { min-width: 0; border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); padding: 24px; }
	.inspector-head, .section-head, .prepare { display: flex; align-items: start; justify-content: space-between; gap: 18px; }
	.inspector h2 { margin: 0; font: 500 27px Fraunces, Georgia, serif; }
	.inspector h3 { margin: 0; font-size: 16px; }
	.editor { display: grid; gap: 14px; margin-top: 24px; }
	label { display: grid; gap: 6px; color: var(--ink-2); font-size: 11px; font-weight: 600; }
	label small { color: var(--ink-3); font-weight: 400; }
	input, textarea, select { box-sizing: border-box; width: 100%; border: 1px solid var(--rule); border-radius: 6px; background: var(--paper); color: var(--ink); font-size: 13px; padding: 9px 10px; }
	textarea { min-height: 70px; resize: vertical; }
	.editor > button { justify-self: start; }
	.dependencies { border-top: 1px solid var(--rule); margin-top: 24px; padding-top: 20px; }
	.dependencies ul { margin: 10px 0 0; padding-left: 17px; }
	.dependencies li { color: var(--ink-2); font-size: 12px; line-height: 1.6; }
	.dependencies p:last-child { color: var(--ink-2); font-size: 12px; }
	.shape, .prepare { border-top: 1px solid var(--rule); margin-top: 26px; padding-top: 22px; }
	.prepare { align-items: center; }
	.regenerate { display: grid; min-width: min(100%, 360px); gap: 8px; }
	.regenerate button { justify-self: end; }
	.prepare p:last-child { margin: 6px 0 0; color: var(--ink-2); font-size: 12px; }
	.ready-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
	.hint { margin: 6px 0 0; color: var(--ink-3); font-size: 12px; }
	.dirty-hint { color: var(--amber); font-size: 12px; margin-bottom: 12px; }
	.conflict { border: 1px solid #e2b9ae; border-radius: 10px; background: #f8e9e5; color: #873f30; margin-bottom: 18px; padding: 16px 18px; }
	.conflict h2 { margin: 0; font: 500 22px Fraunces, Georgia, serif; color: inherit; }
	.conflict-actions { display: flex; gap: 8px; margin-top: 12px; }
	.empty { border: 1px dashed var(--rule); border-radius: 10px; padding: 54px 28px; text-align: center; }
	.empty h2 { margin: 0; font: 500 28px Fraunces, Georgia, serif; }
	.empty > p:last-of-type { max-width: 590px; margin: 12px auto 20px; color: var(--ink-2); font-size: 14px; line-height: 1.6; }
	.error { border: 1px solid #e2b9ae; border-radius: 7px; background: #f8e9e5; color: #873f30; margin-bottom: 18px; padding: 10px 12px; font-size: 13px; }
	.chat-edit { border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); margin-top: 22px; padding: 18px; }
	.chat-edit form { display: flex; gap: 8px; margin-top: 10px; }
	.chat-edit input { flex: 1; }
	.chat-note { margin: 10px 0 0; color: var(--ink-2); font-size: 12px; line-height: 1.5; }
	.chat-disabled { margin: 10px 0 0; color: var(--ink-3); font-size: 12px; }
	.confirm-backdrop { position: fixed; z-index: 50; inset: 0; display: grid; place-items: center; background: rgb(18 23 21 / .48); padding: 18px; }
	.confirm-dialog { width: min(100%, 470px); border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); box-shadow: 0 20px 60px rgb(0 0 0 / .18); padding: 22px; }
	.confirm-dialog h2 { margin: 0; font: 500 25px Fraunces, Georgia, serif; }
	.confirm-dialog > p:not(.eyebrow) { color: var(--ink-2); font-size: 13px; line-height: 1.5; }
	.confirm-dialog > div { display: flex; justify-content: end; gap: 8px; margin-top: 18px; }
	@media (max-width: 840px) { .workspace { grid-template-columns: 1fr; } .path-list { position: static; } .path-list ol { grid-template-columns: repeat(2, 1fr); } }
	@media (max-width: 640px) { .unit-page { padding: 28px 16px 60px; } .unit-head, .head-actions, .inspector-head, .section-head, .prepare, .lock-in-bar { align-items: stretch; flex-direction: column; } .history-panel .section-head > p { text-align: left; } .path-list ol { grid-template-columns: 1fr; } .inspector { padding: 18px; } .chat-edit form { flex-direction: column; } }
</style>
