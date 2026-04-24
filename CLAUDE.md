# Journey Planner — Project Context

> Global context: ~/.claude/CLAUDE.md (sameer-brain repo)

## What It Does
Multi-modal route optimizer + AI travel advisor.
Compares car/train/bus/flight across cost, time, CO2 for any origin-destination pair.
Google Maps Distance Matrix API with Haversine fallback for offline use.
Greedy nearest-neighbour algorithm for multi-stop route optimization.
AI travel advisor (multi-turn chat) + AI packing checklist via Ollama.

## Stack
Python, Streamlit, Google Maps Distance Matrix API, Ollama

## Structure
- app.py — main app, 5 tabs: Route Planner / Multi-Stop / AI Advisor / Packing List / About
- services/maps.py — Google Maps API + Haversine fallback

## Key Conventions
- Model selector: format_func=_model_label
- inject_tab_bg_switcher() — full-screen tab backgrounds
- Footer: sameerbhalerao.com · Soul Spark · Google Maps APIs · GitHub
- About tab: Portfolio button (amber #f59e0b) first

## Secrets Required
- .streamlit/secrets.toml: GOOGLE_MAPS_API_KEY

## Deployment
Streamlit Cloud — auto-deploys on push to main (github.com/sameervb/journey-planner)

## Recent Changes (Apr 2026)
- Added sameerbhalerao.com to footer and About tab
- _model_label() added
