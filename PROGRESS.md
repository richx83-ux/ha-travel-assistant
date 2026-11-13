# Travel Assistant – Development Progress

**Last updated:** 2026-11-13  
**Current version:** 3.0.19  
**Repository:** [richx83-ux/ha-travel-assistant](https://github.com/richx83-ux/ha-travel-assistant)

## v3.0.19
- Live trip: on the last stop of the day, if it is accommodation (cruise ship, hotel, home, etc.), hide "Ready to depart" and show "End day" / "Finish trip" instead. You stay overnight without marking a departure.

## v3.0.18
- Offline install: clearer guidance when a 401 (expired Home Assistant session) blocks pinning the offline app.

## v3.0.17
- Fixed live trip stuck on "Loading…": restored missing `_active_day` helper so `/api/trips/{id}/live` works.
- Live trip page now shows an error message instead of infinite Loading if the API fails.

## v3.0.16
- Fixed "Refresh from postcodes" on categories (get_locations was not injected into API routes, so the endpoint crashed).
- Refresh button now shows how many places were updated.

## v3.0.15
- Packing: Add from store cupboard is hidden behind an Add button next to Back.

## v3.0.14
- Packing: Add from store cupboard (multi-select existing items) instead of creating new ones.

## v3.0.13
- Packing: Remove button on each item so you can drop something you decide not to take (does not affect the store cupboard).

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
