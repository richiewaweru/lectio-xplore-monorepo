import { describe, expect, it } from 'vitest';

import { componentRegistry } from '../schema/registry';
import { teacherFor } from './teacher-facing';

describe('teacher-facing metadata', () => {
	it('covers every registry component id', () => {
		for (const component of Object.values(componentRegistry)) {
			expect(() => teacherFor(component.id)).not.toThrow();
		}
	});

	it('includes teacher-facing entries for newly added media components', () => {
		expect(teacherFor('video-embed')).toEqual({
			teacherLabel: 'Video',
			teacherDescription: 'Embed a YouTube or Vimeo video with a caption.'
		});

		expect(teacherFor('image-block')).toEqual({
			teacherLabel: 'Image',
			teacherDescription: 'Photo, screenshot, or illustration from an uploaded image.'
		});
	});
});
