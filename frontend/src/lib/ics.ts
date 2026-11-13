/**
 * Daily reminders as one iCalendar (.ics) file, made on the device. Times are "floating" local
 * time (no time zone), so 08:00 stays 08:00 wherever the phone is. The app never suggests times.
 */
export type Reminder = { title: string; time: string };

/** Escape text for an iCalendar value (RFC 5545, 3.3.11). */
export function escapeText(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/\r?\n/g, "\\n").replace(/([,;])/g, "\\$1");
}

/** Fold lines longer than 75 octets (RFC 5545, 3.1), never splitting a character. */
export function foldLine(line: string): string {
  const encoder = new TextEncoder();
  const parts: string[] = [];
  let current = "";
  let size = 0;
  for (const ch of line) {
    const bytes = encoder.encode(ch).length;
    const limit = parts.length === 0 ? 75 : 74; // continuation lines start with a space
    if (size + bytes > limit) {
      parts.push(current);
      current = "";
      size = 0;
    }
    current += ch;
    size += bytes;
  }
  parts.push(current);
  return parts.join("\r\n ");
}

const pad = (n: number) => String(n).padStart(2, "0");

function utcStamp(d: Date): string {
  return `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}${pad(d.getUTCSeconds())}Z`;
}

function localDate(d: Date): string {
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`;
}

/** One VEVENT per reminder, repeating every day from `start` (today by default). */
export function buildIcs(reminders: Reminder[], options: { now?: Date; start?: Date; uidPrefix?: string } = {}): string {
  const now = options.now ?? new Date();
  const start = options.start ?? now;
  const prefix = options.uidPrefix ?? `${now.getTime().toString(36)}`;
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//MedWise BD//My Medicines//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
  ];
  reminders.forEach((reminder, i) => {
    const [hh, mm] = reminder.time.split(":");
    lines.push(
      "BEGIN:VEVENT",
      `UID:${prefix}-${i}@medwise-bd`,
      `DTSTAMP:${utcStamp(now)}`,
      `DTSTART:${localDate(start)}T${hh}${mm}00`,
      "DURATION:PT5M",
      "RRULE:FREQ=DAILY",
      `SUMMARY:${escapeText(reminder.title)}`,
      "BEGIN:VALARM",
      "ACTION:DISPLAY",
      `DESCRIPTION:${escapeText(reminder.title)}`,
      "TRIGGER:PT0M",
      "END:VALARM",
      "END:VEVENT",
    );
  });
  lines.push("END:VCALENDAR");
  return lines.map(foldLine).join("\r\n") + "\r\n";
}

/** Reminder titles: the medicine, or a neutral title when names are hidden. */
export function reminderTitle(
  medicine: { brandName: string; strength: string },
  hideNames: boolean,
  neutralTitle: string,
): string {
  return hideNames ? neutralTitle : `${medicine.brandName} ${medicine.strength}`;
}

/** One all-day event (the follow-up visit) with a reminder the day before; made on the device. */
export function buildDayEventIcs(date: string, title: string, options: { now?: Date } = {}): string {
  const now = options.now ?? new Date();
  const [y, m, d] = date.split("-").map(Number);
  const start = new Date(y, m - 1, d);
  const end = new Date(y, m - 1, d + 1);
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//MedWise BD//Prescription//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "BEGIN:VEVENT",
    `UID:${now.getTime().toString(36)}-followup@medwise-bd`,
    `DTSTAMP:${utcStamp(now)}`,
    `DTSTART;VALUE=DATE:${localDate(start)}`,
    `DTEND;VALUE=DATE:${localDate(end)}`,
    `SUMMARY:${escapeText(title)}`,
    "BEGIN:VALARM",
    "ACTION:DISPLAY",
    `DESCRIPTION:${escapeText(title)}`,
    "TRIGGER:-P1D",
    "END:VALARM",
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  return lines.map(foldLine).join("\r\n") + "\r\n";
}
