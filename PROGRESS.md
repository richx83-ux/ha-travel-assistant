# Travel Assistant – Development Progress

**Last updated:** 2026-11-10  
**Current version:** 3.0.12  
**Repository:** [richx83-ux/ha-travel-assistant](https://github.com/richx83-ux/ha-travel-assistant)

## v3.0.12
- Packing: add extra items directly while packing (does not overwrite packed progress).
- Grok recommendations not in the store: buttons to add to cupboard or to the current trip.

## v3.0.11
- Bag editor: multi-select existing store-cupboard items (grouped by category) to add to a bag at once.

## v3.0.10
- Bag editor: add existing store cupboard items to a bag (instead of only creating new ones). Remove from bag button added.

## v3.0.0
- Removed the old Jinja/HTML UI entirely.
- React dashboard is the only UI (served at `/` → `/react`).
- All API endpoints retained.
- Achievements page removed (to be rebuilt in the React UI later).
