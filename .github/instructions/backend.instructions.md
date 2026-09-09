---
description: Lean ERP backend rules
applyTo: 'backend/**/*.py'
---

Follow root AGENTS.md. Preserve project scope, role filtering, audit history, soft deletion and monetary ledger immutability. Business writes use service transactions and ActionReceipt; tests are registered once in scripts/ci/backend_test_matrix.py. Never bypass schema_guard or operate on an old database.
