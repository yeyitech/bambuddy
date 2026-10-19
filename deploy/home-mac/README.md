# Household console on Mac mini

All Git development, builds, commits and pushes occur on mac-1.
The operator laptop has no checkout or commits for this fork.

The native /home-ledger page adds authenticated, admin-only purchase editing,
staged spool purchase/cost views, historical task evidence and a quality case view.
Unknown weights remain null; the extension does not create native inventory
spools, deduct usage or send printer commands. History entries are candidate
filename groups and must be resolved to real runs before archiving.

Runtime files live outside Git under a private service-state directory:
data/home-ledger-seed.json initializes data/home-ledger.sqlite once. Subsequent
edits use SQLite transactions, optimistic revisions and an audit trail.
Back up this database alongside bambuddy.db and archive files.

Build the frontend on mac-1 using npm ci and npm run build, then build
deploy/home-mac/Dockerfile with BASE_IMAGE pinned to an upstream image digest.
The overlay registers only the new backend module; it does not replace upstream
main.py. Set BAMBUDDY_IMAGE and BAMBUDDY_STATE in a private environment file.
Deploy compose.yaml in bridge mode. Port 8130 is local/LAN only.
Printer credentials and login secrets must never be committed.

Implemented: view existing imported records, edit purchase fields, retain audit.
Pending: create/delete purchases, photos and experiment editing, native spool
binding, historical archive import, DNS/TLS ingress, automated backup scheduling.
