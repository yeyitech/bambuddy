# Household console on Mac mini

All Git development, builds, commits and pushes occur on mac-1.
Runtime databases, receipt manifests, session tokens and photographs stay outside Git.

The native /home-ledger page provides purchase editing, inventory-backed stock,
historical evidence, quality notes, and a 用料与损耗 tab. Inventory and Statistics
also show the material accounting summary. Unknown starting weights remain unknown
while consumed grams continue accumulating.

## Material accounting

backend/app/services/home_material_accounting.py is a stdlib-only SQLite worker.
It runs once per minute in the material-accounting Compose sidecar, with networking disabled. Both writers use the same Linux VM filesystem/locking environment; never run a native macOS SQLite writer against the active container WAL database.
It does not connect to the printer or issue MQTT commands.

Inputs:
- native print_log_entries (one record per actual run), spool_usage_history;
- archived sliced 3MF files;
- private job storage-readback-verification.json plus matching mqtt-start-intent.json.
  The receipt filename, dispatch hash and actual bytes must agree;
- optional private data/home-material-policy.json for reviewed historical mappings.

The worker copies verified device readbacks into the console archive while a print
is running, so the native completion tracker can consume its actual slicing metadata.
Slots are snapshotted only when their assignment predates the run. Past missing
mappings require reviewed explicit evidence; current slot colors do not prove which
physical roll an old run used.

After completion, native usage wins. If native usage is absent, a completed sole run
with exact source/mapping can be reconciled. Partial failures without native usage
remain pending. An IMMEDIATE transaction commits stock debit, native usage records,
and a unique per-run receipt together. Opening balances are converted to history
without being debited again. Do not blindly replay historical import policies against
a different database.

Material weights are slicer estimates, not scale readings. G-code feature extrusion
classifies model/support/tower/brim and Bambu VFLUSH annotations classify planned
purge. Unknown commands/custom startup purges remain unclassified. Classified
grams are subsets of the slicer total and never additional inventory debits.
Aggregate loss is mass-weighted over covered runs and excludes missing breakdowns.
The UI labels it 已识别损耗率 rather than complete actual waste.
Authenticated admins can record collected waste weight with an audit trail.
This changes waste statistics only; it does not debit the same material again.

The current print is shown as planned consumption. It is not charged before completion.
Imported inventory weight locks prevent coarse AMS percentages from overwriting
history/scale estimates; they do not disable per-print consumption tracking.

## Build / deploy

Build frontend on mac-1 with npm run typecheck and npm run build.
deploy/home-mac/build.sh builds the overlay on the pinned upstream image; it registers
the isolated backend route and services without replacing upstream main.py.
Configure BAMBUDDY_IMAGE and BAMBUDDY_STATE outside Git; deploy compose.yaml in bridge
mode. Port 8130 is local/LAN only. The printer runs independently of this service.

The Compose sidecar mounts the native data directory read/write and job receipts read-only. The Python worker requires no third-party modules.
It writes heartbeat and reports into the native SQLite database. Back up bambuddy.db,
home-ledger.sqlite, home-material-policy.json and archive files together using SQLite
backup (not a raw copy of a live WAL database).

Validation: python3 tests/test_home_material_accounting.py.
Never point tests or replay simulations at the production database.

Limitations:
- Missing original slices (e.g. old cloud-only records) cannot yield a trustworthy
  waste breakdown; manual weighing may fill those records.
- Third-party spool net weights and unknown procurement costs must be confirmed.
- Prints sent by another tool without matching slices/mappings remain pending rather
  than silently deducting guessed amounts.
