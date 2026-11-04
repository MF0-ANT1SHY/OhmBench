import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools' / 'extend'))
from derive_groundtruth import changed_lines, innermost, scopes  # noqa: E402

SOURCE = """import { a } from 'b'
export class Store {
  private items: string[] = []
  // a comment with { brace
  async load(id: number): Promise<void> {
    const s = '}'
    for (const x of this.items) {
      console.info(`${x}`)
    }
  }
  build() {
    Column() {
      Text('x')
    }
  }
}
export function helper(n: number) {
  return n + 1
}
"""

PATCH = """diff --git a/src/Store.ets b/src/Store.ets
--- a/src/Store.ets
+++ b/src/Store.ets
@@ -7,3 +7,4 @@ export class Store {
-    for (const x of this.items) {
+    for (const x of this.items.slice(0, 10)) {
+      // bounded
       console.info(`${x}`)
@@ -17,2 +18,2 @@
-export function helper(n: number) {
+export function helper(n: number): number {
"""


class DeriveTest(unittest.TestCase):
    def test_scopes(self):
        found = {(k, n): (s, e, p) for k, n, s, e, p in scopes(SOURCE)}
        self.assertEqual(found[("type", "Store")][:2], (2, 16))
        self.assertEqual(found[("function", "load")], (5, 10, "Store"))
        self.assertEqual(found[("function", "build")], (11, 15, "Store"))
        self.assertEqual(found[("function", "helper")][:2], (17, 19))

    def test_changed_lines_map_to_functions(self):
        points = changed_lines(PATCH)["src/Store.ets"]
        found = scopes(SOURCE)
        names = {innermost(found, a, b)[1] for a, b in points}
        self.assertEqual(names, {"load", "helper"})


if __name__ == "__main__":
    unittest.main()