import test from "node:test";
import assert from "node:assert/strict";
import {daysUntilNoticeDate} from "./driverDates.js";

test("notice reminders distinguish today, tomorrow and past dates across London midnight", () => {
  const noon = new Date("2026-10-24T12:00:00Z");
  assert.equal(daysUntilNoticeDate("2026-10-24", noon), 0);
  assert.equal(daysUntilNoticeDate("2026-10-25", noon), 1);
  assert.equal(daysUntilNoticeDate("2026-10-23", noon), -1);
  assert.equal(daysUntilNoticeDate("2026-10-25", new Date("2026-10-24T23:30:00Z")), 0);
  assert.equal(daysUntilNoticeDate("2026-10-26", new Date("2026-10-25T23:30:00Z")), 1);
});
