export const TIME_ZONE = 'Europe/London';
const partsFormat = new Intl.DateTimeFormat('en-GB', {
  timeZone: TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

export function londonInput(date) {
  const parts = Object.fromEntries(partsFormat.formatToParts(date).map(p => [p.type, p.value]));
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

export function londonToISO(value) {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) throw new Error('Please choose a valid deadline.');
  const naive = Date.parse(`${value}:00Z`);
  if (!Number.isFinite(naive)) throw new Error('Please choose a valid deadline.');
  // UK UTC offsets are 0/+1. Reject spring-forward gaps; choose the later
  // occurrence during autumn's repeated hour, giving the full requested window.
  const candidates = [naive - 3600000, naive].filter(ms => londonInput(new Date(ms)) === value);
  if (!candidates.length) throw new Error('That time does not exist due to the UK clock change.');
  return new Date(Math.max(...candidates)).toISOString();
}

export function clock(value) {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: TIME_ZONE, hour: '2-digit', minute: '2-digit'
  }).format(new Date(value));
}

export function fullDate(value) {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: TIME_ZONE, day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
  }).format(new Date(value));
}

export function pence(value) {
  return value == null ? '—' : `${value.toFixed(1).replace(/\.0$/, '')}p`;
}

export function calendar(plan) {
  const stamp = value => new Date(value).toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
  return ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Ready, Set, Wash//Personal Planner//EN', 'BEGIN:VEVENT', `UID:${crypto.randomUUID()}@ready-set-wash.local`, `DTSTAMP:${stamp(new Date())}`, `DTSTART:${stamp(plan.start)}`, `DTEND:${stamp(plan.end)}`, 'SUMMARY:Start your wash', 'DESCRIPTION:Ready, Set, Wash suggested this window. Start your machine yourself.', 'BEGIN:VALARM', 'TRIGGER:-PT5M', 'ACTION:DISPLAY', 'DESCRIPTION:Your wash starts in five minutes', 'END:VALARM', 'END:VEVENT', 'END:VCALENDAR', ''].join('\r\n');
}
