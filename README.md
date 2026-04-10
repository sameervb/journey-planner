<div align="center">

# 🗺️ Journey Planner

**Multi-modal route optimizer and AI travel advisor — compare car, train, bus, and flight for any journey. No account needed.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Google Maps](https://img.shields.io/badge/Google_Maps_API-optional-4285F4?style=flat&logo=googlemaps&logoColor=white)](https://developers.google.com/maps)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-black?style=flat)](https://ollama.ai)
[![License](https://img.shields.io/badge/license-MIT-22c55e?style=flat)](LICENSE)

[**Portfolio**](https://sameerbhalerao.com) · [**Soul Spark**](https://soulspark.me) · [**LinkedIn**](https://linkedin.com/in/sameervb) · [**GitHub**](https://github.com/sameervb)

</div>

---

## What It Does

Journey Planner helps you decide *how* to travel — not just where. Enter any two cities and instantly compare **car, train, bus, and flight** across journey time, cost per person, and CO₂ emissions. Planning a multi-stop road trip? The optimizer sequences your waypoints for the shortest total route. Need packing advice or travel tips? The AI advisor handles it all in a multi-turn chat.

Works offline (Haversine distance estimates) and without any API keys. Everything degrades gracefully.

---

## Features

| Tab | What you get |
|-----|-------------|
| **🗺️ Route Planner** | Compare all four transport modes — time, cost/person, CO₂. Smart recommendation card highlights the best option. Scales cost correctly for group travel. |
| **🔀 Multi-Stop** | Add any number of waypoints. Greedy nearest-neighbour algorithm finds the optimal visit sequence and draws the full route summary. |
| **🤖 AI Advisor** | Multi-turn travel advisor chat. Ask about routes, accommodation, timing, visa requirements, local tips — anything. |
| **🎒 Packing List** | Describe your trip and destination. Get a fully categorised AI packing checklist: clothing, documents, tech, toiletries, extras. |
| **ℹ️ About** | Project context and links. |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| UI & hosting | Streamlit |
| Distance & routing | Google Maps Distance Matrix API · Haversine great-circle fallback |
| Geocoding | Google Maps Geocoding API · 50+ city offline coordinate lookup |
| Multi-stop optimization | Greedy nearest-neighbour algorithm |
| AI | Ollama (local LLM) via Cloudflare Tunnel |
| Language | Python 3.10+ |

---

## Transport Model

| Mode | Avg speed | Cost basis | CO₂/km |
|------|-----------|------------|--------|
| 🚗 Car | 90 km/h | €0.112/km | 0.162 kg |
| 🚆 Train | 120 km/h | €0.15/km | 0.041 kg |
| 🚌 Bus | 70 km/h | €0.08/km | 0.068 kg |
| ✈️ Flight | 700 km/h + 2.5h overhead | €80 base + €0.10/km | 0.255 kg |

Figures are European averages. Traveller count scales total cost correctly.

---

## Quick Start

```bash
git clone https://github.com/sameervb/journey-planner
cd journey-planner
pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Both keys are optional — see Secrets section below

streamlit run app.py
```

---

## Secrets

```toml
# .streamlit/secrets.toml

# Optional — enables live driving distances instead of Haversine estimates
GOOGLE_MAPS_API_KEY = ""

# Optional — enables AI Advisor and Packing List tabs
OLLAMA_BASE_URL = "https://your-tunnel.trycloudflare.com"
OLLAMA_MODEL    = "llama3.1:8b"
```

**Both secrets are optional.** The app degrades gracefully:

- No Maps key → distances use Haversine formula (great-circle estimate)
- No Ollama → AI tabs show a "Connect AI" prompt, all other tabs work normally

---

## Deploying to Streamlit Cloud

1. Fork / push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → New App → select this repo
3. Under **Advanced settings → Secrets**, paste:

```toml
OLLAMA_BASE_URL    = "https://your-cloudflare-url.trycloudflare.com"
OLLAMA_MODEL       = "llama3.1:8b"
GOOGLE_MAPS_API_KEY = ""   # optional
```

### Cloudflare Tunnel — expose local Ollama to the cloud

```bash
# Run on your machine while Ollama is running on port 11434
cloudflared tunnel --url http://localhost:11434
```

Paste the generated `*.trycloudflare.com` URL as `OLLAMA_BASE_URL` in Streamlit Cloud secrets.

---

## Architecture

```
Browser → Streamlit Cloud
    │
    ├── Route Planner ─── Google Maps Distance Matrix API
    │                  └── Haversine formula (offline fallback)
    │
    ├── Multi-Stop ─────── Greedy nearest-neighbour optimizer
    │                   └── Google Maps multi-point Distance Matrix
    │
    ├── AI Advisor ─────── Cloudflare Tunnel ──→ Ollama (your machine)
    │                   └── Multi-turn conversation with context
    │
    └── Packing List ───── Cloudflare Tunnel ──→ Ollama (your machine)
                        └── Streamed AI response

No user data stored. No authentication required.
All LLM inference runs on your local machine.
```

---

## Project Context

Built as a standalone portfolio app, part of a series extracted from [Soul Spark](https://soulspark.me) — a local-first personal intelligence platform integrating finance, health, career, and travel into a unified conversational AI advisor.

**Related apps in this series:**
- [jd-analyzer](https://github.com/sameervb/jd-analyzer) — Resume-to-JD fit scorer and cover letter generator
- [dota-analyzer](https://github.com/sameervb/dota-analyzer) — Dota 2 player stats and draft intelligence

---

<div align="center">

Built by [Sameer Bhalerao](https://sameerbhalerao.com) · Senior Analytics & AI Product Leader · Amazon L6 BIE · Luxembourg

</div>
