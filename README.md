# Travel Assistant – Home Assistant Add-on

A modern theme-based place tracker and future road-trip planner for Home Assistant.

## Features (v0.1.0)

- Create and manage **Themes** (e.g. English Heritage Sites)
- Add **Places** to each theme (name, coordinates, address, visit duration, opening hours, notes)
- Mark places as **Visited** with an optional **Visit Date**
- One-click toggle for visited status
- Progress bar (X of Y places + %)
- Interactive map of places with coordinates (OpenStreetMap)
- Clean modern UI (not the default Home Assistant look)

## Installation

1. In Home Assistant go to **Settings → Add-ons → Add-on Store**
2. Click the three dots (⋮) in the top right → **Repositories**
3. Add this repository URL:

   ```
   https://github.com/richx83-ux/ha-travel-assistant
   ```

4. Find **Travel Assistant** in the store and click **Install**
5. Start the add-on and enable **Show in sidebar**
6. Open it from the sidebar

## Data

All data is stored in SQLite inside the add-on's persistent storage and is included in Home Assistant backups.

## Development

This is the early MVP focused on Theme Admin + Places Admin with visit tracking.
Future versions will add the trip planner, CSV import, photo uploads, and deeper Home Assistant integrations.
