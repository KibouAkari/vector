import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { conversationGroups } from "../lib/chat-history-groups.mjs";

const at = (year, month, day, hour = 12) =>
  new Date(year, month - 1, day, hour).toISOString();

test("chat history groups by the viewer's local day", () => {
  const items = [
    { id: "a", updated_at: at(2026, 10, 14, 9) },
    { id: "b", updated_at: at(2026, 10, 13, 22) },
    { id: "c", updated_at: at(2026, 10, 10, 18) },
    { id: "d", updated_at: at(2026, 9, 9) }
  ];
  const groups = conversationGroups(items, new Date(2026, 9, 14, 17));
  assert.deepEqual(groups.map(x => x.label), [
    "Today", "Yesterday", "Previous 7 days", "September 2026"
  ]);
  assert.deepEqual(groups.flatMap(x => x.items.map(c => c.id)), [
    "a", "b", "c", "d"
  ]);
  assert.deepEqual(items.map(x => x.id), ["a", "b", "c", "d"]);
});

test("missing timestamps and empty history have safe states", () => {
  assert.deepEqual(conversationGroups([]), []);
  const groups = conversationGroups([{ id: "untimed" }]);
  assert.equal(groups[0].label, "Earlier");
  assert.equal(groups[0].items[0].id, "untimed");
});

test("chat file downloads keep URL validation and accessible actions", () => {
  const artifact = readFileSync(
    new URL("../components/ui/vector-chat-artifact.js", import.meta.url),
    "utf8"
  );
  assert.match(artifact, /originalUrl\.startsWith\("\/"\)/);
  assert.match(artifact, /originalUrl\.startsWith\("\/\/"\)/);
  assert.match(artifact, /aria-label=\{\`Download/);
  assert.match(artifact, /download=\{name\}/);
});
