# Travel Assistant – Home Assistant Add-on (v2)

A polished, modern theme-based place tracker, trip planner, and travel companion for Home Assistant.

## What's New in v2

- **Refined UI/UX**: Dark mode support, improved typography (Inter), softer shadows, better cards, consistent button styles, and enhanced visual hierarchy.
- **Better mobile experience**: Improved touch targets, responsive layout, and sidebar behaviour.
- **Design system**: Reusable card, button, and progress components for consistency across pages.
- **Accessibility & polish**: Higher contrast options, smoother transitions, and cleaner empty states.
- Core functionality remains fully compatible with v1 data.

## Features

- Create and manage **Categories/Themes** (e.g. English Heritage, Superchargers, Hotels)
- Add **Places** with coordinates, opening hours, photos, visit duration
- Mark places as **Visited** with photo proof and dates
- **Achievements** and gamification (county/region/country completion)
- **Trip Planner** with multi-day itineraries, OSRM routing, time calculations, and live mode
- **Packing lists** / Store cupboard with kit templates
- Interactive **maps** (Leaflet + OpenStreetMap)
- CSV import, photo uploads, custom UI colours
- Clean modern UI designed for both desktop and mobile (including HA Companion app)

## Installation

1. In Home Assistant go to **Settings → Add-ons → Add-on Store**
2. Click the three dots (⋮) → **Repositories**
3. Add: `https://github.com/richx83-ux/ha-travel-assistant`
4. Install **Travel Assistant**, start it, and enable **Show in sidebar**

All data is stored in SQLite in the add-on's persistent storage and is included in Home Assistant backups.

## Development Notes

This is a FastAPI + Jinja2 + Tailwind application packaged as a Home Assistant add-on.
