type DateParts = {local: string; offset: string};

const ISO_LOCAL = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,9}))?)?$/;
const ISO_OFFSET = /^(?:Z|[+-](?:0\d|1\d|2[0-3]):[0-5]\d)$/;

function validLocal(value: string): boolean {
  const match = ISO_LOCAL.exec(value);
  if (!match) return false;
  const [, year, month, day, hour, minute, second = '0'] = match;
  const y = Number(year), m = Number(month), d = Number(day);
  const h = Number(hour), min = Number(minute), sec = Number(second);
  const leap = y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return y > 0 && m >= 1 && m <= 12 && d >= 1 && d <= days[m - 1]
    && h <= 23 && min <= 59 && sec <= 59;
}

export function splitIsoOffset(value: string): DateParts {
  const match = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?)(Z|[+-]\d{2}:\d{2})$/.exec(value);
  if (!match || !validLocal(match[1]) || !ISO_OFFSET.test(match[2])) {
    throw new Error('Die gespeicherte Zeit hat keinen gültigen ausdrücklichen Zeitzonen-Offset.');
  }
  return {local:match[1].slice(0, 16), offset:match[2]};
}

export function buildIsoOffset(local: string, offset: string, original: string | null | undefined): string {
  if (!validLocal(local)) throw new Error('Bitte ein gültiges Datum und eine gültige Uhrzeit angeben.');
  if (!ISO_OFFSET.test(offset)) throw new Error('Bitte für diese Zeit einen ausdrücklichen Zeitzonen-Offset wählen.');
  if (original) {
    try {
      const before = splitIsoOffset(original);
      if (before.local === local && before.offset === offset) return original;
    } catch { /* Rebuild only after the user explicitly supplies a valid offset. */ }
  }
  const minutePrecision = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(local);
  return `${local}${minutePrecision ? ':00' : ''}${offset}`;
}

export function offsetOptions(existing?: string | null): Array<{value: string; label: string}> {
  const result = [
    {value:'Z',label:'UTC'},
    {value:'+01:00',label:'MEZ (UTC+01:00)'},
    {value:'+02:00',label:'MESZ (UTC+02:00)'},
  ];
  if (existing && ISO_OFFSET.test(existing) && !result.some(item => item.value === existing)) {
    result.push({value:existing,label:`Vorhandener Offset (${existing})`});
  }
  return result;
}
