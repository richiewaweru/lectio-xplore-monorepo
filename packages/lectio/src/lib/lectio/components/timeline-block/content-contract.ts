import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		title: {
			format: 'plain_text',
			description: 'Timeline title.',
			renderBehavior: 'Plain text.'
		},
		intro: {
			format: 'plain_text',
			description: 'Optional introduction to the sequence.',
			renderBehavior: 'Plain text.'
		},
		'events[].id': {
			format: 'plain_text_short',
			description: 'Stable identifier for the event row.',
			renderBehavior: 'Plain text key.'
		},
		'events[].year': {
			format: 'plain_text_short',
			description: 'Date, era, or sequence label.',
			renderBehavior: 'Plain text label column.'
		},
		'events[].title': {
			format: 'plain_text',
			description: 'Event headline.',
			renderBehavior: 'Plain text.'
		},
		'events[].summary': {
			format: 'plain_text',
			description: 'Concise description of the event.',
			renderBehavior: 'Plain text.'
		},
		'events[].impact': {
			format: 'plain_text',
			description: 'Optional impact or consequence line.',
			renderBehavior: 'Plain text.'
		},
		'events[].tags': {
			format: 'structured_array',
			description: 'Optional short tag strings for filtering or emphasis.',
			renderBehavior: 'Plain text entries.'
		},
		'events[].era': {
			format: 'plain_text',
			description: 'Optional era grouping label.',
			renderBehavior: 'Plain text.'
		},
		closing_takeaway: {
			format: 'plain_text',
			description: 'Optional synthesis line after events.',
			renderBehavior: 'Plain text.'
		}
	},
	componentConstraints: [
		'Events should usually appear in chronological order.',
		'Each event should have a stable id.'
	]
} satisfies LectioContentContract;
