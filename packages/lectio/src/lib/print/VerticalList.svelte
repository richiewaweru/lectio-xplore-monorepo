<script lang="ts">
	import type { TimelineEvent } from '$lib/schema/types';

	let {
		events,
		title = undefined
	}: { events: TimelineEvent[]; title?: string } = $props();
</script>

<div class="vertical-list">
	{#if title}
		<h4 class="list-title">{title}</h4>
	{/if}

	{#each events as event}
		<div class="event timeline-print-event" data-print-item="timeline-event">
			<div class="event-marker">
				<div class="year">{event.year}</div>
				{#if event.era}
					<div class="era">{event.era}</div>
				{/if}
			</div>
			<div class="event-content">
				<h5 class="event-title">{event.title}</h5>
				<p class="event-summary">{event.summary}</p>
				{#if event.impact}
					<p class="event-impact"><strong>Impact:</strong> {event.impact}</p>
				{/if}
			</div>
		</div>
	{/each}
</div>

<style>
	.vertical-list {
		margin: 1rem 0;
	}

	.list-title {
		font-size: 1.125rem;
		font-weight: 600;
		margin-bottom: 1rem;
	}

	.event {
		display: flex;
		gap: 1.5rem;
		margin-bottom: 1.5rem;
		page-break-inside: avoid;
		border-left: 3px solid #e5e7eb;
		padding-left: 1rem;
	}

	.event-marker {
		flex-shrink: 0;
		width: 5rem;
	}

	.year {
		font-weight: 700;
		font-size: 1.125rem;
	}

	.era {
		font-size: 0.75rem;
		color: #6b7280;
		margin-top: 0.25rem;
	}

	.event-content {
		flex: 1;
	}

	.event-title {
		font-weight: 600;
		margin-bottom: 0.5rem;
	}

	.event-summary {
		line-height: 1.6;
		margin-bottom: 0.5rem;
	}

	.event-impact {
		font-size: 0.875rem;
		font-style: italic;
	}

	@media print {
		.event {
			border-left-color: #9ca3af;
		}
	}
</style>
