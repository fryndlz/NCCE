'use strict';
// The campaign calendar is a display projection; raw timestamps remain in data.
const NCCEWriting = (() => {
  const months = 'January February March April May June July August September October November December'.split(' ');
  function formatDate(value, meaningfulTime) {
    if (!value) return {imperialDisplay: 'Date unrecorded', realDisplay: ''};
    const raw = String(value), dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(raw);
    const placeholder = meaningfulTime === undefined && /T00:00:00(?:\.0+)?$/.test(raw);
    let parts;
    if (dateOnly || /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(raw)) {
      const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2}))?)?/);
      parts = {year: +match[1], month: +match[2], day: +match[3], hour: dateOnly || placeholder ? 12 : +match[4], minute: +match[5] || 0, second: +match[6] || 0};
      const check = new Date(Date.UTC(parts.year, parts.month - 1, parts.day));
      if (check.getUTCFullYear() !== parts.year || check.getUTCMonth() !== parts.month - 1 || check.getUTCDate() !== parts.day || parts.hour > 23 || parts.minute > 59 || parts.second > 59) return {imperialDisplay:'Date unverified', realDisplay:'Source date could not be interpreted'};
    } else {
      const instant = new Date(raw);
      if (Number.isNaN(instant.getTime())) return {imperialDisplay: 'Date unverified', realDisplay: 'Source date could not be interpreted'};
      parts = Object.fromEntries(new Intl.DateTimeFormat('en-GB', {timeZone: 'Europe/Warsaw', year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric', second: 'numeric', hourCycle: 'h23'}).formatToParts(instant).filter(p => p.type !== 'literal').map(p => [p.type, Number(p.value)]));
    }
    const wall = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second);
    const fraction = Math.max(0, Math.min(999, Math.floor((wall - Date.UTC(parts.year, 0, 1)) / (Date.UTC(parts.year + 1, 0, 1) - Date.UTC(parts.year, 0, 1)) * 1000)));
    let show = meaningfulTime === undefined ? !dateOnly && !/T00:00:00(?:\.0+)?$/.test(raw) : Boolean(meaningfulTime) && !dateOnly;
    const real = `${parts.day} ${months[parts.month-1]} ${parts.year}` + (show ? ` · ${String(parts.hour).padStart(2, '0')}:${String(parts.minute).padStart(2, '0')}` : '');
    return {imperialDisplay: `9.${String(fraction).padStart(3, '0')}.998.M41`, realDisplay: real, fraction, sourceTimestamp: value};
  }
  function recordDate(record) {
    if (record.date_display) return record.date_display;
    if (record.is_baseline || record.baseline || /baseline/i.test(record.event_type || '')) return {imperialDisplay: 'Undated archive', realDisplay: 'Known at baseline · occurrence date unknown'};
    const occurred = record.occurred_at || record.event_date || record.date;
    const result = formatDate(occurred || record.observed_at || record.generated_at);
    if (!occurred && record.observed_at) result.realDisplay += ' · first observed; occurrence date unknown';
    return result;
  }
  return {formatDate, recordDate};
})();
