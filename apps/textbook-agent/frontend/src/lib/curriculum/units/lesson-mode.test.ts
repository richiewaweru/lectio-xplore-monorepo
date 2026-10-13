import { describe, expect, it } from 'vitest';
import { effectiveLessonMode, lessonModeLabel, lessonModeNote } from './lesson-mode';

describe('lesson-mode helpers', () => {
	it('uses the stored valid mode, else first exposure', () => {
		expect(effectiveLessonMode({ lesson_mode: 'consolidation' })).toBe('consolidation');
		expect(effectiveLessonMode({ lesson_mode: null })).toBe('first_exposure');
		expect(effectiveLessonMode({})).toBe('first_exposure');
		expect(effectiveLessonMode({ lesson_mode: 'bogus' })).toBe('first_exposure');
		expect(effectiveLessonMode(null)).toBe('first_exposure');
	});

	it('labels modes', () => {
		expect(lessonModeLabel('first_exposure')).toBe('First exposure');
		expect(lessonModeLabel('retrieval')).toBe('Retrieval');
	});

	it('shows a note only when both mode and reason exist', () => {
		expect(lessonModeNote({ lesson_mode: 'repair', lesson_mode_reason: 'Fix the gap.' })).toBe('Repair: Fix the gap.');
		expect(lessonModeNote({ lesson_mode: 'repair', lesson_mode_reason: '  ' })).toBeNull();
		expect(lessonModeNote({ lesson_mode: null, lesson_mode_reason: 'x' })).toBeNull();
		expect(lessonModeNote({})).toBeNull();
	});
});
