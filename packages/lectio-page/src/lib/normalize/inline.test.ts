import { describe, expect, it } from 'vitest';
import { asRichText, plainText } from './inline';

describe('inline normalization', () => {
  it('converts legacy emphasis tags into typed nodes', () => {
    expect(asRichText('A <strong>claim</strong> and <em>evidence</em>.')).toEqual([
      { type: 'text', value: 'A ' },
      { type: 'strong', children: [{ type: 'text', value: 'claim' }] },
      { type: 'text', value: ' and ' },
      { type: 'emphasis', children: [{ type: 'text', value: 'evidence' }] },
      { type: 'text', value: '.' }
    ]);
  });

  it('preserves the visible text while removing raw markup', () => {
    const value = '<strong>Evidence</strong> supports the claim.';
    expect(plainText(value)).toBe('Evidence supports the claim.');
    expect(JSON.stringify(asRichText(value))).not.toContain('<strong>');
  });

  it('renders markdown emphasis from legacy string fields', () => {
    expect(asRichText('A **key idea**.')).toEqual([
      { type: 'text', value: 'A ' },
      { type: 'strong', children: [{ type: 'text', value: 'key idea' }] },
      { type: 'text', value: '.' }
    ]);
  });
});
