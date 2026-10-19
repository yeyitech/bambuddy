import { describe, it, expect } from 'vitest';
import { resolvePrintDisplayName } from './printName';
describe('print display names', () => {
  const raw = 'checked-00a0bc55-21c7-4546-8bef-d3f679e35125-Kitty-White-R3';
  it('uses the exact archived title without modifying file identity', () => {
    expect(resolvePrintDisplayName(raw, [{filename: raw+'.3mf', print_name:'Hello Kitty 白色盘'}])).toBe('Hello Kitty 白色盘');
  });
  it('never matches a different version by partial title', () => {
    expect(resolvePrintDisplayName(raw, [{filename:raw+'-old.3mf',print_name:'旧版'}])).toBe('Kitty-White-R3');
  });
  it('keeps unknown names intact and handles ordinary extensions', () => {
    expect(resolvePrintDisplayName('Hello Kitty.gcode.3mf')).toBe('Hello Kitty');
    expect(resolvePrintDisplayName('checked-not-a-uuid-model')).toBe('checked-not-a-uuid-model');
    expect(resolvePrintDisplayName(null)).toBe('');
  });
});
