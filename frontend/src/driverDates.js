// Compare calendar dates in the product's England coverage, including DST.
export function daysUntilNoticeDate(value, now = new Date()) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(now).map(part => [part.type, part.value]));
  const today = Date.UTC(Number(parts.year), Number(parts.month) - 1, Number(parts.day));
  return Math.round((Date.parse(`${value}T00:00:00Z`) - today) / 86400000);
}
