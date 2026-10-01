# KUD governance code that lives in the database

These files are **copies**, not a module. The code runs from `ir.cron` /
`ir.actions.server` records on production and has no XML ID, so no module
update can overwrite it - and nothing in this folder is loaded by Odoo.

They are here so the code has a history outside the database.

| File | Production record | Deployed |
|---|---|---|
| `cron_238_autorec_guard.py` | `ir.cron` 238 - KUD AUTOREC guard | 2026-09-23, sha256 `012d497aec54fdaa...` |

The guard's previous code is kept on production in the system parameter
`kud_autorec.guard_v1_pre_alert_20260923`.
