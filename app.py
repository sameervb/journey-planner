"""
Journey Planner — Standalone Streamlit App
Single & multi-stop route optimiser, AI travel advisor, and packing checklist.
Powered by Google Maps APIs + local Ollama AI.
"""
from __future__ import annotations

import json
import time
import base64
from datetime import date, datetime
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components

from services.maps import (
    geocode, get_driving_data, estimate_modes, optimize_route,
    format_duration, TRANSPORT_MODES, FALLBACK_COORDS,
)

st.set_page_config(
    page_title="Journey Planner",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Asset loader ───────────────────────────────────────────────────────────────
def _b64(filename: str) -> str:
    p = Path(__file__).parent / "assets" / filename
    if p.exists():
        ext = p.suffix.lstrip(".")
        mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "avif": "avif"}.get(ext, "jpeg")
        return f"data:image/{mime};base64," + base64.b64encode(p.read_bytes()).decode()
    return ""

@st.cache_data(show_spinner=False)
def load_assets():
    return {
        "overview": _b64("overview.jpg"),
        "network":  _b64("network.jpg"),
        "hero":     _b64("hero.jpg"),
    }

IMG         = load_assets()
overview_bg = f"url('{IMG['overview']}')" if IMG["overview"] else "none"
network_bg  = f"url('{IMG['network']}')"  if IMG["network"]  else "none"
hero_bg     = f"url('{IMG['hero']}')"     if IMG["hero"]     else "none"

def inject_tab_bg_switcher(tab_imgs: list):
    """Inject JS that swaps full-screen app background per active tab.
    tab_imgs: list of raw data-URI strings (one per tab, in order).
    Uses a stacked gradient overlay to keep text readable.
    """
    imgs_js = json.dumps(tab_imgs)
    components.html(f"""
    <script>
    (function() {{
      var IMGS = {imgs_js};
      var OVERLAY = 'linear-gradient(rgba(7,9,15,0.72), rgba(7,9,15,0.72))';
      function applyBg(idx) {{
        var app = window.parent.document.querySelector('[data-testid="stAppViewContainer"]');
        if (!app) return;
        var img = IMGS[idx] || '';
        if (img) {{
          app.style.backgroundImage = OVERLAY + ", url('" + img + "')";
          app.style.backgroundSize = 'cover';
          app.style.backgroundPosition = 'center top';
          app.style.backgroundAttachment = 'fixed';
          app.style.backgroundRepeat = 'no-repeat';
        }}
      }}
      function setupObserver() {{
        var tabList = window.parent.document.querySelector('[data-baseweb="tab-list"]');
        if (!tabList) {{ setTimeout(setupObserver, 250); return; }}
        function syncActive() {{
          var tabs = tabList.querySelectorAll('[data-baseweb="tab"]');
          for (var i = 0; i < tabs.length; i++) {{
            if (tabs[i].getAttribute('aria-selected') === 'true') {{ applyBg(i); break; }}
          }}
        }}
        syncActive();
        new MutationObserver(syncActive).observe(tabList, {{
          attributes: true, subtree: true, attributeFilter: ['aria-selected']
        }});
      }}
      setupObserver();
    }})();
    </script>
    """, height=0, scrolling=False)

# ══════════════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
*, *::before, *::after { font-family: 'Inter', sans-serif; box-sizing: border-box; }

[data-testid="stAppViewContainer"] {
    background: #07090f;
    background-size: cover !important;
    background-position: center top !important;
    background-attachment: fixed !important;
    background-repeat: no-repeat !important;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #090d1a 0%, #07090f 100%);
    border-right: 1px solid #1a2236;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 2px; background: #0d1120; padding: 5px;
    border-radius: 14px; border: 1px solid #1a2236;
}
.stTabs [data-baseweb="tab"] {
    background: transparent; border-radius: 10px;
    color: #4b5a7a; border: none; padding: 9px 22px;
    font-weight: 600; font-size: 0.82rem; letter-spacing: 0.02em;
    transition: all 0.2s;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%) !important;
    color: #fff !important;
    box-shadow: 0 4px 16px rgba(14,165,233,0.4);
}

/* ── Section header ── */
.sec-hdr {
    display: flex; align-items: center; gap: 12px;
    margin: 28px 0 16px;
}
.sec-title {
    font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.14em; color: #4b5a7a; white-space: nowrap;
}
.sec-line { flex: 1; height: 1px; background: linear-gradient(90deg, #1e2d42, transparent); }

/* ── Mode card ── */
.mode-card {
    background: linear-gradient(135deg, #0f1825, #111d2e);
    border: 1px solid #1e2d42; border-radius: 16px;
    padding: 20px; position: relative; overflow: hidden;
    transition: border-color 0.2s;
}
.mode-card.recommended {
    border-color: #0ea5e9;
    box-shadow: 0 0 20px rgba(14,165,233,0.12);
}
.mode-card .accent-top {
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
    border-radius: 16px 16px 0 0;
}
.mode-label { font-size: 1.1rem; font-weight: 800; color: #f1f5f9; margin-bottom: 14px; }
.mode-metric { display: flex; justify-content: space-between; margin-bottom: 6px; }
.mode-metric-key { color: #4b5a7a; font-size: 0.8rem; }
.mode-metric-val { color: #e2e8f0; font-size: 0.85rem; font-weight: 600; }
.mode-badge {
    display: inline-block; font-size: 0.68rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.08em;
    padding: 3px 10px; border-radius: 20px; margin-top: 8px;
}

/* ── Route segment card ── */
.seg-card {
    background: linear-gradient(135deg, #0a1020, #0d1428);
    border: 1px solid #1a2236; border-radius: 12px;
    padding: 14px 18px; margin-bottom: 10px;
    display: flex; align-items: center; gap: 16px;
}
.seg-arrow { color: #0ea5e9; font-size: 1.1rem; }
.seg-loc { flex: 1; }
.seg-from { font-size: 0.78rem; color: #64748b; }
.seg-name { font-size: 0.92rem; font-weight: 700; color: #e2e8f0; }
.seg-stats { text-align: right; }
.seg-km { font-size: 0.88rem; font-weight: 700; color: #0ea5e9; }
.seg-time { font-size: 0.75rem; color: #4b5a7a; }

/* ── Packing item ── */
.pack-cat {
    font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.12em; color: #4b5a7a; margin: 18px 0 8px;
}
.pack-progress-bar {
    height: 6px; border-radius: 4px;
    background: linear-gradient(90deg, #0ea5e9, #0284c7);
}

/* ── AI output ── */
.ai-output {
    background: linear-gradient(135deg, #0a1020, #0d1428);
    border: 1px solid #1a2236; border-left: 3px solid #0ea5e9;
    border-radius: 12px; padding: 20px 24px;
    color: #cbd5e1; line-height: 1.75; font-size: 0.9rem;
    margin-top: 12px;
}
.lore-box {
    background: linear-gradient(135deg, #0a1528, #0d1e38);
    border: 1px solid #1a3050; border-left: 3px solid #38bdf8;
    border-radius: 12px; padding: 16px 20px;
    color: #93c5fd; font-style: italic; font-size: 0.88rem;
    line-height: 1.7; margin-bottom: 12px;
}

/* ── Chat ── */
.chat-bubble-user {
    background: linear-gradient(135deg, #0e2a4a, #0d2240);
    border: 1px solid #1a3050; border-radius: 16px 16px 4px 16px;
    padding: 12px 16px; color: #bae6fd; font-size: 0.88rem;
    max-width: 80%; margin-left: auto; margin-bottom: 10px;
}
.chat-bubble-ai {
    background: linear-gradient(135deg, #0a1020, #0d1428);
    border: 1px solid #1a2236; border-radius: 16px 16px 16px 4px;
    padding: 12px 16px; color: #cbd5e1; font-size: 0.88rem;
    max-width: 85%; margin-bottom: 10px;
}

/* ── KPI card ── */
.kpi-card {
    background: linear-gradient(135deg, #0f1825, #111d2e);
    border: 1px solid #1e2d42; border-radius: 14px;
    padding: 18px 16px; position: relative; overflow: hidden;
    text-align: center;
}
.kpi-card .accent-bar {
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
}
.kpi-val { font-size: 1.6rem; font-weight: 900; line-height: 1; margin: 8px 0 4px; }
.kpi-lbl { font-size: 0.72rem; color: #4b5a7a; text-transform: uppercase; letter-spacing: 0.1em; }

/* ── Footer ── */
.footer {
    text-align: center; padding: 28px 0 16px;
    font-size: 0.78rem; color: #334155; line-height: 2;
    border-top: 1px solid #1a2236; margin-top: 32px;
}
.footer a { color: #0ea5e9; text-decoration: none; }
.footer strong { color: #64748b; }

/* ── Step badge ── */
.step-badge {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 14px; border-radius: 12px; margin-bottom: 8px;
    border: 1px solid transparent;
}
.step-badge.done   { background: rgba(14,165,233,0.08); border-color: rgba(14,165,233,0.2); }
.step-badge.active { background: rgba(14,165,233,0.05); border-color: #1e2d42; }
.step-badge.locked { opacity: 0.4; }
.step-num {
    width: 26px; height: 26px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.75rem; font-weight: 700; flex-shrink: 0;
    background: #1e2d42; color: #64748b;
}
.step-badge.done   .step-num { background: #0ea5e9; color: #fff; }
.step-badge.active .step-num { background: #0c2030; color: #38bdf8; border: 1px solid #0ea5e9; }
.step-label { font-size: 0.82rem; font-weight: 600; color: #e2e8f0; }
.step-sub   { font-size: 0.72rem; color: #4b5a7a; }

/* ── Empty state ── */
.empty-state {
    background: linear-gradient(135deg, #0f1825, #111d2e);
    border: 1px solid #1e2d42; border-radius: 16px;
    padding: 48px; text-align: center;
    display: flex; flex-direction: column; align-items: center;
}
.empty-icon { font-size: 2.5rem; margin-bottom: 12px; }
.empty-title { font-size: 1rem; font-weight: 700; color: #e2e8f0; margin-bottom: 6px; }
.empty-sub { color: #4b5a7a; font-size: 0.84rem; max-width: 380px; line-height: 1.6; }

/* ── Tab banner ── */
.tab-banner {
    border-radius: 20px; overflow: hidden; position: relative;
    margin-bottom: 28px; height: 180px;
    background-size: cover; background-position: center;
    display: flex; align-items: flex-end;
    background-color: #0c1628; border: 1px solid #1a2e4a;
}
.tab-banner .banner-overlay { position: absolute; inset: 0; }
.tab-banner .banner-content { position: relative; z-index: 1; padding: 28px 32px; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# Config helpers
# ══════════════════════════════════════════════════════════════════════════════
def _maps_key() -> str:
    try:
        return st.secrets.get("GOOGLE_MAPS_API_KEY", "") or st.secrets.get("google", {}).get("maps_api_key", "")
    except Exception:
        return ""

def _ollama_url() -> str:
    try:
        return st.secrets.get("OLLAMA_BASE_URL", "") or st.secrets.get("ollama", {}).get("base_url", "")
    except Exception:
        return ""

def _ollama_model() -> str:
    override = st.session_state.get("journey_model")
    if override:
        return override
    try:
        return st.secrets.get("OLLAMA_MODEL", "") or st.secrets.get("ollama", {}).get("model", "llama3.1:8b")
    except Exception:
        return "llama3.1:8b"

MAPS_KEY  = _maps_key()
AI_ON     = bool(_ollama_url())

# ══════════════════════════════════════════════════════════════════════════════
# Ollama streaming helpers (identical pattern across all portfolio apps)
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=30, show_spinner=False)
def detect_models() -> list[str]:
    url = _ollama_url()
    if not url: return []
    try:
        r = requests.get(f"{url.rstrip('/')}/api/tags", timeout=5)
        if r.ok:
            return sorted(m["name"] for m in r.json().get("models", []))
    except Exception:
        pass
    return []

@st.cache_data(ttl=15, show_spinner=False)
def detect_gpu() -> bool | None:
    url = _ollama_url()
    if not url: return None
    try:
        r = requests.get(f"{url.rstrip('/')}/api/ps", timeout=5)
        if r.ok:
            models = r.json().get("models", [])
            if not models: return None
            return any(m.get("size_vram", 0) > 0 for m in models)
    except Exception:
        pass
    return None

def _stream(prompt: str, system: str = "", max_tokens: int = 1000, temp: float = 0.72):
    url = _ollama_url()
    if not url:
        yield "⚠️ OLLAMA_BASE_URL not set in Streamlit secrets."
        return
    try:
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
        r = requests.post(
            f"{url.rstrip('/')}/api/chat",
            json={"model": _ollama_model(), "messages": msgs, "stream": True,
                  "options": {"num_predict": max_tokens, "temperature": temp}},
            timeout=120, stream=True,
        )
        if r.ok:
            for line in r.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token: yield token
                        if chunk.get("done"): break
                    except Exception:
                        pass
        else:
            yield f"⚠️ Ollama HTTP {r.status_code}"
    except requests.Timeout:
        yield "⚠️ **Timeout** — try phi3:mini or mistral for faster responses."
    except requests.ConnectionError:
        yield "⚠️ **Cannot reach Ollama.** Check OLLAMA_BASE_URL in secrets."
    except Exception as e:
        yield f"⚠️ {e}"

def _stream_multi_turn(messages: list[dict], max_tokens: int = 700, temp: float = 0.72):
    url = _ollama_url()
    if not url:
        yield "⚠️ OLLAMA_BASE_URL not set."
        return
    try:
        r = requests.post(
            f"{url.rstrip('/')}/api/chat",
            json={"model": _ollama_model(), "messages": messages, "stream": True,
                  "options": {"num_predict": max_tokens, "temperature": temp}},
            timeout=120, stream=True,
        )
        if r.ok:
            for line in r.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token: yield token
                        if chunk.get("done"): break
                    except Exception:
                        pass
        else:
            yield f"⚠️ Ollama HTTP {r.status_code}"
    except requests.Timeout:
        yield "⚠️ Timeout — try phi3:mini for faster responses."
    except requests.ConnectionError:
        yield "⚠️ Cannot reach Ollama. Check tunnel URL."
    except Exception as e:
        yield f"⚠️ {e}"


def render_ai(prompt: str, system: str = "", max_tokens: int = 1000,
              temp: float = 0.72, lore: bool = False) -> str:
    start = time.perf_counter()
    status = st.status("⚡ Generating...", expanded=True)
    full = ""
    with status:
        full = st.write_stream(_stream(prompt, system, max_tokens, temp))
        elapsed = time.perf_counter() - start
        st.caption(f"Generated in {elapsed:.1f}s · Model: {_ollama_model()}")
    status.update(label=f"✅ Done · {elapsed:.1f}s", state="complete", expanded=False)
    full = full or ""
    if full.startswith("⚠️"):
        st.warning(full)
        return full
    if lore and "---" in full:
        parts = full.split("---", 1)
        st.markdown(f'<div class="lore-box">✨ {parts[0].strip()}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="ai-output">{parts[1].strip()}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="ai-output">{full}</div>', unsafe_allow_html=True)
    return full

# ══════════════════════════════════════════════════════════════════════════════
# UI helpers
# ══════════════════════════════════════════════════════════════════════════════
def sec(title: str, icon: str = ""):
    st.markdown(
        f'<div class="sec-hdr"><span class="sec-title">{icon}&nbsp;{title}</span>'
        f'<div class="sec-line"></div></div>',
        unsafe_allow_html=True,
    )

def banner(title: str, subtitle: str, accent: str = "#0ea5e9", tag: str = "Journey Planner", bg: str = "none"):
    img_style = f"background-image:{bg};" if bg != "none" else ""
    st.markdown(f"""
    <div class="tab-banner" style="{img_style}">
        <div class="banner-overlay"
             style="background:linear-gradient(to right,rgba(7,9,15,0.94) 0%,rgba(7,9,15,0.65) 55%,rgba(7,9,15,0.2) 100%)"></div>
        <div class="banner-content">
            <div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;
                        letter-spacing:0.18em;color:{accent};margin-bottom:8px">{tag}</div>
            <div style="font-size:1.75rem;font-weight:800;color:#f1f5f9;line-height:1.1">{title}</div>
            <div style="color:#94a3b8;margin-top:6px;font-size:0.84rem;max-width:520px">{subtitle}</div>
        </div>
    </div>""", unsafe_allow_html=True)

def kpi(icon: str, label: str, value: str, color: str = "#0ea5e9"):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="accent-bar" style="background:linear-gradient(90deg,{color},transparent)"></div>
        <div style="font-size:1.4rem;margin-top:10px">{icon}</div>
        <div class="kpi-val" style="color:{color}">{value}</div>
        <div class="kpi-lbl">{label}</div>
    </div>""", unsafe_allow_html=True)

def footer():
    st.markdown("""
    <div class="footer">
        Built by <strong>Sameer Bhalerao</strong> · Senior Analytics & AI Product Leader · Amazon L6<br>
        Part of the <a href="https://soulspark.me" target="_blank">Soul Spark</a> portfolio ·
        Data: <a href="https://developers.google.com/maps" target="_blank">Google Maps APIs</a> ·
        <a href="https://github.com/sameervb/journey-planner" target="_blank">GitHub</a> ·
        No login required · No data stored
    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    if IMG["overview"]:
        st.markdown(f"""
        <div style="border-radius:16px;overflow:hidden;margin-bottom:16px;height:110px;
                    background-image:{overview_bg};background-size:cover;background-position:center">
            <div style="height:100%;background:linear-gradient(to bottom,rgba(7,9,15,0.3),rgba(7,9,15,0.88));
                        display:flex;flex-direction:column;justify-content:flex-end;padding:14px">
                <div style="font-size:0.6rem;font-weight:700;text-transform:uppercase;
                            letter-spacing:0.2em;color:#0ea5e9">AI-Powered</div>
                <div style="font-size:1.1rem;font-weight:800;color:#f1f5f9;line-height:1.2">Journey Planner</div>
                <div style="color:#4b5a7a;font-size:0.72rem;margin-top:2px">No login · No data stored</div>
            </div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="margin-bottom:20px">
            <div style="font-size:0.65rem;font-weight:700;text-transform:uppercase;
                        letter-spacing:0.2em;color:#0ea5e9;margin-bottom:6px">AI-Powered</div>
            <div style="font-size:1.3rem;font-weight:800;color:#f1f5f9;line-height:1">Journey Planner</div>
            <div style="color:#4b5a7a;font-size:0.78rem;margin-top:4px">No login · No data stored</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div style="height:1px;background:linear-gradient(90deg,#1e2d42,transparent);margin-bottom:16px"></div>', unsafe_allow_html=True)

    # Workflow steps
    has_route      = bool(st.session_state.get("route_result"))
    has_multistop  = bool(st.session_state.get("multistop_result"))
    has_packing    = bool(st.session_state.get("packing_list"))
    has_chat       = bool(st.session_state.get("advisor_history"))

    steps = [
        (1, "Route Planner",  "Compare transport modes",  has_route),
        (2, "Multi-Stop",     "Optimise waypoint order",  has_multistop),
        (3, "AI Advisor",     "Travel intelligence chat", has_chat),
        (4, "Packing List",   "AI-generated checklist",   has_packing),
    ]
    html = ""
    for num, label, sub, done in steps:
        cls   = "done" if done else "active"
        check = "✓" if done else str(num)
        html += f"""
        <div class="step-badge {cls}">
            <div class="step-num">{check}</div>
            <div>
                <div class="step-label">{label}</div>
                <div class="step-sub">{sub}</div>
            </div>
        </div>"""
    st.markdown(html, unsafe_allow_html=True)

    st.markdown('<div style="height:1px;background:linear-gradient(90deg,#1e2d42,transparent);margin:12px 0"></div>', unsafe_allow_html=True)

    # Saved route summary
    if has_route:
        r = st.session_state["route_result"]
        st.markdown(f"""
        <div style="background:rgba(14,165,233,0.08);border:1px solid rgba(14,165,233,0.2);
                    border-radius:12px;padding:12px 14px;margin-bottom:12px">
            <div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:0.1em;
                        color:#4b5a7a;margin-bottom:2px">Active Route</div>
            <div style="font-size:0.82rem;font-weight:700;color:#e2e8f0">
                {r.get("origin","?")} → {r.get("destination","?")}
            </div>
            <div style="font-size:0.75rem;color:#4b5a7a">{r.get("distance_km","?")} km</div>
        </div>""", unsafe_allow_html=True)

    if st.button("🔄 Clear All", use_container_width=True):
        for k in ["route_result", "route_analysis", "multistop_result", "multistop_analysis",
                  "advisor_history", "advisor_context", "packing_list", "packing_checked",
                  "packing_analysis"]:
            st.session_state.pop(k, None)
        st.rerun()

    st.markdown('<div style="height:1px;background:linear-gradient(90deg,#1e2d42,transparent);margin:12px 0"></div>', unsafe_allow_html=True)

    if MAPS_KEY:
        st.markdown('<div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.2);border-radius:10px;padding:8px 12px;color:#86efac;font-size:0.78rem;margin-bottom:8px">🟢 &nbsp;Google Maps live</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="background:#0d1520;border:1px solid #1e2d42;border-radius:10px;padding:8px 12px;color:#4b5a7a;font-size:0.78rem;margin-bottom:8px">🔵 &nbsp;Haversine mode (no Maps key)</div>', unsafe_allow_html=True)

    _MODEL_DESC = {
        "phi3:mini":     "⚡ fastest · ~5s",
        "phi3:medium":   "⚡ fast · ~10s",
        "mistral":       "⚖️ balanced · ~15s",
        "mistral:7b":    "⚖️ balanced · ~15s",
        "llama3.1:8b":   "🧠 capable · ~30s",
        "llama3.1:70b":  "🧠 most capable · slow",
        "llama3:8b":     "🧠 capable · ~30s",
        "gemma:7b":      "⚖️ balanced · ~20s",
        "gemma2:9b":     "⚖️ balanced · ~20s",
        "qwen2.5:7b":    "⚖️ balanced · ~20s",
        "deepseek-r1":   "🔬 reasoning · slow",
    }
    def _model_label(m: str) -> str:
        if m in _MODEL_DESC:
            return f"{m} — {_MODEL_DESC[m]}"
        n = m.lower()
        if any(x in n for x in ["34b","70b","72b","65b","40b"]): hint = "🐘 large · ~2m+"
        elif any(x in n for x in ["13b","14b","20b","30b"]): hint = "🧠 capable · ~1m"
        elif any(x in n for x in ["7b","8b","9b"]): hint = "⚖️ balanced · ~30s"
        elif any(x in n for x in ["3b","4b","6b"]): hint = "⚡ fast · ~15s"
        elif any(x in n for x in ["mini","tiny","small","nano"]): hint = "⚡ fastest · ~5s"
        elif "llava" in n: hint = "👁️ vision · ~30s"
        elif "deepseek" in n: hint = "🔬 reasoning · slow"
        elif "code" in n: hint = "💻 code · ~20s"
        elif any(x in n for x in ["neural","orca","chat"]): hint = "💬 chat · ~20s"
        elif any(x in n for x in ["mistral","llama","gemma","qwen","phi"]): hint = "⚖️ balanced · ~20s"
        else: hint = "🤖 ~20s"
        return f"{m} — {hint}"

    if AI_ON:
        models = detect_models()
        gpu    = detect_gpu()
        gpu_lbl = "🟩 GPU" if gpu is True else "🟨 CPU" if gpu is False else ""
        st.markdown(f'<div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.2);border-radius:10px;padding:8px 12px;color:#86efac;font-size:0.78rem;margin-bottom:8px">🟢 &nbsp;AI online &nbsp;{gpu_lbl}</div>', unsafe_allow_html=True)
        if models:
            current = _ollama_model()
            idx = models.index(current) if current in models else 0
            chosen = st.selectbox(
                "Model", models, index=idx,
                label_visibility="collapsed",
                format_func=_model_label,
            )
            if chosen != st.session_state.get("journey_model"):
                st.session_state["journey_model"] = chosen
    else:
        st.markdown('<div style="background:#0d1520;border:1px solid #1e2d42;border-radius:10px;padding:8px 12px;color:#4b5a7a;font-size:0.78rem">🔵 &nbsp;Set OLLAMA_BASE_URL for AI</div>', unsafe_allow_html=True)

    st.markdown("")
    st.caption("Streamlit · Google Maps · Ollama · Cloudflare Tunnel")


# ══════════════════════════════════════════════════════════════════════════════
# Tabs
# ══════════════════════════════════════════════════════════════════════════════
tab_route, tab_multi, tab_advisor, tab_pack, tab_about = st.tabs([
    "🗺️ Route Planner", "🔀 Multi-Stop", "🤖 AI Advisor", "🎒 Packing List", "ℹ️ About"
])

# Tab 0→overview, 1→network, 2→network, 3→hero, 4→overview
inject_tab_bg_switcher([
    IMG["overview"], IMG["network"], IMG["network"], IMG["hero"], IMG["overview"]
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Route Planner
# ══════════════════════════════════════════════════════════════════════════════
with tab_route:
    banner(
        "Route Planner",
        "Compare car, train, bus, and flight for any journey — cost, time, and CO₂.",
        accent="#0ea5e9",
        tag="Transport Comparison",
        bg=overview_bg,
    )

    with st.form("route_form"):
        c1, c2 = st.columns(2)
        with c1:
            origin = st.text_input("Origin", placeholder="e.g. London", key="r_origin")
        with c2:
            destination = st.text_input("Destination", placeholder="e.g. Paris", key="r_dest")
        c3, c4, c5 = st.columns([2, 2, 1])
        with c3:
            dep_date = st.date_input("Departure", value=date.today(), key="r_date")
        with c4:
            travelers = st.number_input("Travellers", min_value=1, max_value=10, value=1, key="r_travelers")
        with c5:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Compare Routes →", use_container_width=True, type="primary")

    if submitted:
        if not origin or not destination:
            st.warning("Please enter both origin and destination.")
        else:
            with st.spinner("Computing routes..."):
                origin_coords = geocode(origin, MAPS_KEY)
                dest_coords   = geocode(destination, MAPS_KEY)

                if not origin_coords or not dest_coords:
                    st.error(f"Could not geocode one or both locations. Try a major city name.")
                else:
                    from services.maps import haversine_km
                    straight_km  = haversine_km(*origin_coords, *dest_coords)
                    driving_data = get_driving_data(origin, destination, MAPS_KEY) if MAPS_KEY else None
                    modes        = estimate_modes(straight_km, driving_data)
                    road_km      = driving_data["distance_km"] if driving_data else straight_km

                    st.session_state["route_result"] = {
                        "origin":      origin,
                        "destination": destination,
                        "distance_km": round(straight_km, 1),
                        "road_km":     round(road_km, 1),
                        "modes":       modes,
                        "travelers":   travelers,
                        "dep_date":    dep_date.isoformat(),
                    }
                    st.session_state.pop("route_analysis", None)
                    st.rerun()

    result = st.session_state.get("route_result")
    if result:
        sec("Route Summary", "📍")

        # KPI row
        modes = result["modes"]
        best_mode  = min(modes, key=lambda k: modes[k]["co2_kg"])
        cheap_mode = min(modes, key=lambda k: modes[k]["cost_eur"])
        fast_mode  = min(modes, key=lambda k: modes[k]["time_h"])

        k1, k2, k3, k4 = st.columns(4)
        with k1: kpi("📏", "Straight-line", f"{result['distance_km']} km")
        with k2: kpi("🛣️", "Road distance", f"{result['road_km']} km", color="#f59e0b")
        with k3: kpi("⚡", "Fastest mode", modes[fast_mode]["label"].split()[1], color="#8b5cf6")
        with k4: kpi("🌿", "Greenest mode", modes[best_mode]["label"].split()[1], color="#22c55e")

        sec("Mode Comparison", "🚦")

        cols = st.columns(len(modes))
        for col, (mode_key, m) in zip(cols, modes.items()):
            is_cheap  = mode_key == cheap_mode
            is_green  = mode_key == best_mode
            is_fast   = mode_key == fast_mode
            is_rec    = is_cheap
            rec_class = "recommended" if is_rec else ""
            cost_total = m["cost_eur"] * result["travelers"]

            badges = ""
            if is_cheap: badges += '<span class="mode-badge" style="background:rgba(34,197,94,0.15);color:#4ade80">Cheapest</span> '
            if is_green: badges += '<span class="mode-badge" style="background:rgba(34,197,94,0.1);color:#86efac">Greenest</span> '
            if is_fast:  badges += '<span class="mode-badge" style="background:rgba(139,92,246,0.15);color:#c4b5fd">Fastest</span> '
            travelers_row = f'<div class="mode-metric"><span class="mode-metric-key">Total ({result["travelers"]}p)</span><span class="mode-metric-val">€{round(cost_total)}</span></div>' if result["travelers"] > 1 else ""

            # Build as single-line HTML — multiline indented HTML triggers Markdown code-block mode
            card = (
                f'<div class="mode-card {rec_class}">'
                f'<div class="accent-top" style="background:{m["color"]}"></div>'
                f'<div class="mode-label">{m["label"]}</div>'
                f'<div class="mode-metric"><span class="mode-metric-key">Duration</span><span class="mode-metric-val">{format_duration(m["time_h"])}</span></div>'
                f'<div class="mode-metric"><span class="mode-metric-key">Cost / person</span><span class="mode-metric-val">€{m["cost_eur"]:.0f}</span></div>'
                f'{travelers_row}'
                f'<div class="mode-metric"><span class="mode-metric-key">CO₂</span><span class="mode-metric-val">{m["co2_kg"]:.1f} kg</span></div>'
                f'<div>{badges}</div>'
                f'</div>'
            )
            with col:
                st.markdown(card, unsafe_allow_html=True)

        # AI analysis
        if AI_ON:
            sec("AI Travel Intelligence", "🤖")
            if st.session_state.get("route_analysis"):
                st.markdown(f'<div class="ai-output">{st.session_state["route_analysis"]}</div>', unsafe_allow_html=True)
                if st.button("🔄 Regenerate", key="regen_route"):
                    st.session_state.pop("route_analysis", None)
                    st.rerun()
            else:
                mode_lines = "\n".join(
                    f"- {m['label']}: {format_duration(m['time_h'])}, €{m['cost_eur']:.0f}/person, {m['co2_kg']:.1f} kg CO₂"
                    for m in modes.values()
                )
                if st.button("🤖 Analyze This Route", type="primary", use_container_width=True, key="analyze_route"):
                    prompt = f"""Journey: {result['origin']} → {result['destination']}
Distance: {result['distance_km']} km straight-line, {result['road_km']} km road
Travellers: {result['travelers']}
Departure: {result['dep_date']}

Transport options:
{mode_lines}

Provide:
1. Which transport mode you recommend and why (balance cost, time, CO₂, experience)
2. Practical tips for the recommended mode (booking windows, peak times, hidden costs)
3. One surprising insight about this specific route
4. Best time of day/week to travel for this journey

Be specific and practical. No generic travel advice."""
                    system = "You are an expert travel strategist with deep knowledge of European and global transport networks. Give specific, actionable advice."
                    out = render_ai(prompt, system=system, max_tokens=800, temp=0.70)
                    if out and not out.startswith("⚠️"):
                        st.session_state["route_analysis"] = out

        # Save to advisor context
        st.session_state["advisor_context"] = {
            "origin":      result["origin"],
            "destination": result["destination"],
            "distance_km": result["distance_km"],
            "modes":       {k: {"time": format_duration(v["time_h"]),
                                "cost": f"€{v['cost_eur']:.0f}",
                                "co2":  f"{v['co2_kg']:.1f} kg"}
                            for k, v in modes.items()},
        }

    footer()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Multi-Stop Optimizer
# ══════════════════════════════════════════════════════════════════════════════
with tab_multi:
    banner(
        "Multi-Stop Optimizer",
        "Enter any number of waypoints — we'll find the shortest, most efficient route order.",
        accent="#8b5cf6",
        tag="Route Optimization",
        bg=network_bg,
    )

    with st.form("multistop_form"):
        c1, c2 = st.columns(2)
        with c1:
            ms_origin = st.text_input("Starting point", placeholder="e.g. London", key="ms_origin")
        with c2:
            ms_dest = st.text_input("Final destination", placeholder="e.g. Berlin", key="ms_dest")
        ms_waypoints_raw = st.text_area(
            "Waypoints (one per line or comma-separated)",
            placeholder="Paris\nAmsterdam\nBrussels",
            height=120,
            key="ms_wps",
        )
        ms_submit = st.form_submit_button("Optimize Route →", use_container_width=True, type="primary")

    if ms_submit:
        # Parse waypoints
        raw = ms_waypoints_raw.strip()
        if "\n" in raw:
            waypoints = [w.strip() for w in raw.split("\n") if w.strip()]
        else:
            waypoints = [w.strip() for w in raw.split(",") if w.strip()]

        if not ms_origin or not ms_dest:
            st.warning("Please enter starting point and final destination.")
        elif not waypoints:
            st.warning("Please enter at least one waypoint.")
        else:
            with st.spinner(f"Optimizing route through {len(waypoints)} stop(s)..."):
                opt = optimize_route(ms_origin, waypoints, ms_dest, MAPS_KEY)
                opt["origin"]      = ms_origin
                opt["destination"] = ms_dest
                opt["waypoints"]   = waypoints
                st.session_state["multistop_result"]   = opt
                st.session_state.pop("multistop_analysis", None)
                st.rerun()

    ms = st.session_state.get("multistop_result")
    if ms:
        sec("Optimised Route", "✅")

        # Summary KPIs
        k1, k2, k3 = st.columns(3)
        with k1: kpi("📍", "Total stops", str(len(ms["ordered_stops"]) - 2), color="#8b5cf6")
        with k2: kpi("📏", "Total distance", f"{ms['total_km']} km", color="#0ea5e9")
        with k3: kpi("⏱️", "Est. drive time", format_duration(ms["total_h"]), color="#f59e0b")

        if ms.get("used_google"):
            st.caption("✅ Distances from Google Maps Distance Matrix")
        else:
            st.caption("ℹ️ Distances estimated via Haversine formula (straight-line)")

        sec("Stop Order", "🗺️")

        # Ordered stops
        stop_html = ""
        for i, stop in enumerate(ms["ordered_stops"]):
            is_origin = i == 0
            is_dest   = i == len(ms["ordered_stops"]) - 1
            icon      = "🟢" if is_origin else ("🔴" if is_dest else "🔵")
            role      = "Start" if is_origin else ("End" if is_dest else f"Stop {i}")
            stop_html += f"""
            <div style="display:flex;align-items:center;gap:14px;padding:10px 0;
                        {'border-bottom:1px solid #1a2236;' if not is_dest else ''}">
                <div style="font-size:1.1rem">{icon}</div>
                <div style="flex:1">
                    <div style="font-size:0.68rem;color:#4b5a7a;text-transform:uppercase;letter-spacing:0.08em">{role}</div>
                    <div style="font-size:0.95rem;font-weight:700;color:#e2e8f0">{stop}</div>
                </div>
                {'<div style="font-size:1rem;color:#0ea5e9">↓</div>' if not is_dest else ''}
            </div>"""
        st.markdown(f'<div style="background:linear-gradient(135deg,#0f1825,#111d2e);border:1px solid #1e2d42;border-radius:16px;padding:16px 20px">{stop_html}</div>', unsafe_allow_html=True)

        sec("Segment Breakdown", "📊")
        for seg in ms["segments"]:
            st.markdown(f"""
            <div class="seg-card">
                <div class="seg-loc">
                    <div class="seg-from">From</div>
                    <div class="seg-name">{seg['from']}</div>
                </div>
                <div class="seg-arrow">→</div>
                <div class="seg-loc">
                    <div class="seg-from">To</div>
                    <div class="seg-name">{seg['to']}</div>
                </div>
                <div class="seg-stats">
                    <div class="seg-km">{seg['distance_km']} km</div>
                    <div class="seg-time">{format_duration(seg['duration_h'])}</div>
                </div>
            </div>""", unsafe_allow_html=True)

        # Show original vs optimised comparison
        original_order = [ms["origin"]] + ms["waypoints"] + [ms["destination"]]
        if original_order != ms["ordered_stops"]:
            sec("Original vs Optimised", "↔️")
            oa, ob = st.columns(2)
            with oa:
                st.markdown('<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:#ef4444;margin-bottom:8px">Original order</div>', unsafe_allow_html=True)
                for s in original_order:
                    st.markdown(f'<div style="padding:6px 0;border-bottom:1px solid #1a2236;color:#64748b;font-size:0.88rem">{s}</div>', unsafe_allow_html=True)
            with ob:
                st.markdown('<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:#22c55e;margin-bottom:8px">Optimised order</div>', unsafe_allow_html=True)
                for s in ms["ordered_stops"]:
                    st.markdown(f'<div style="padding:6px 0;border-bottom:1px solid #1a2236;color:#e2e8f0;font-size:0.88rem">{s}</div>', unsafe_allow_html=True)

        # AI analysis
        if AI_ON:
            sec("AI Route Intelligence", "🤖")
            if st.session_state.get("multistop_analysis"):
                st.markdown(f'<div class="ai-output">{st.session_state["multistop_analysis"]}</div>', unsafe_allow_html=True)
                if st.button("🔄 Regenerate", key="regen_ms"):
                    st.session_state.pop("multistop_analysis", None)
                    st.rerun()
            else:
                if st.button("🤖 Analyze Multi-Stop Route", type="primary", use_container_width=True, key="analyze_ms"):
                    seg_lines = "\n".join(
                        f"- {s['from']} → {s['to']}: {s['distance_km']} km, {format_duration(s['duration_h'])}"
                        for s in ms["segments"]
                    )
                    prompt = f"""Multi-stop road trip route:
Optimised order: {' → '.join(ms['ordered_stops'])}
Total: {ms['total_km']} km, ~{format_duration(ms['total_h'])} driving time

Segments:
{seg_lines}

Provide:
1. Is this route suitable for a single-day drive or does it need splitting over multiple days?
2. Recommended overnight stops if multi-day (name specific cities/towns)
3. The most interesting or must-see thing at 1-2 of the waypoints
4. Practical driving tips (toll roads, border crossings, fuel stops) if relevant
5. Best season or time of year for this specific circuit

Keep it specific and actionable."""
                    system = "You are an experienced road trip planner with expert knowledge of European and global routes, driving conditions, and hidden gems."
                    out = render_ai(prompt, system=system, max_tokens=900, temp=0.70)
                    if out and not out.startswith("⚠️"):
                        st.session_state["multistop_analysis"] = out

    footer()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — AI Advisor
# ══════════════════════════════════════════════════════════════════════════════
with tab_advisor:
    banner(
        "AI Travel Advisor",
        "Ask anything about your journey — transport, accommodation, local tips, timing.",
        accent="#22c55e",
        tag="Travel Intelligence",
        bg=network_bg,
    )

    if not AI_ON:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">🔌</div>
            <div class="empty-title">AI Advisor offline</div>
            <div class="empty-sub">Add OLLAMA_BASE_URL to your Streamlit secrets to enable the AI travel advisor.</div>
        </div>""", unsafe_allow_html=True)
    else:
        # Build context from session
        ctx_parts = []
        route_ctx = st.session_state.get("advisor_context")
        if route_ctx:
            ctx_parts.append(f"Current route: {route_ctx['origin']} → {route_ctx['destination']} ({route_ctx['distance_km']} km)")
            for mode, stats in route_ctx.get("modes", {}).items():
                ctx_parts.append(f"  - {mode}: {stats['time']}, {stats['cost']}, {stats['co2']} CO₂")

        ms_ctx = st.session_state.get("multistop_result")
        if ms_ctx:
            ctx_parts.append(f"Multi-stop route: {' → '.join(ms_ctx['ordered_stops'])} ({ms_ctx['total_km']} km)")

        pack_ctx = st.session_state.get("packing_list")
        if pack_ctx:
            ctx_parts.append(f"Packing list prepared for: {pack_ctx.get('destination', '?')} ({pack_ctx.get('trip_type', '?')} trip, {pack_ctx.get('duration', '?')} days)")

        context_str = "\n".join(ctx_parts) if ctx_parts else "No routes planned yet — user hasn't used the Route Planner or Multi-Stop tabs."

        ADVISOR_SYSTEM = f"""You are Wanderer, an expert AI travel advisor. You are helpful, knowledgeable, and specific.

CURRENT JOURNEY CONTEXT:
{context_str}

Always:
- Reference the user's actual route/destination when relevant
- Give specific, actionable advice — not generic tips
- Mention actual prices, distances, or timings when you know them
- End with the single most important next step for the user

Never give vague advice like "it depends" without following up with specifics."""

        # Quick actions
        sec("Quick Actions", "⚡")
        qa_cols = st.columns(4)
        quick_actions = {
            "Best transport?":     "Based on my route, which transport mode do you recommend and why?",
            "Local tips?":         "What are the top 3 practical tips a first-time visitor should know about my destination?",
            "Best time to go?":    "When is the best time of year to make this journey and why?",
            "Budget breakdown?":   "Give me a realistic daily budget breakdown for my destination including accommodation, food, and transport.",
        }
        for col, (label, prompt) in zip(qa_cols, quick_actions.items()):
            with col:
                if st.button(label, use_container_width=True, key=f"qa_{label}"):
                    history = st.session_state.get("advisor_history", [])
                    history.append({"role": "user", "content": prompt})
                    st.session_state["advisor_history"] = history
                    st.rerun()

        sec("Conversation", "💬")

        history = st.session_state.get("advisor_history", [])
        for msg in history:
            if msg["role"] == "user":
                st.markdown(f'<div class="chat-bubble-user">{msg["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-bubble-ai">{msg["content"]}</div>', unsafe_allow_html=True)

        # Input
        with st.form("advisor_form", clear_on_submit=True):
            user_input = st.text_input("", placeholder="Ask about your journey, destination, packing, visas…",
                                       label_visibility="collapsed", key="advisor_input")
            ask = st.form_submit_button("Send →", use_container_width=True, type="primary")

        if ask and user_input.strip():
            history = st.session_state.get("advisor_history", [])
            history.append({"role": "user", "content": user_input.strip()})

            # Build messages for Ollama
            messages = [{"role": "system", "content": ADVISOR_SYSTEM}]
            for m in history[-10:]:  # keep last 10 turns to manage context
                messages.append(m)

            with st.chat_message("assistant"):
                start = time.perf_counter()
                full = st.write_stream(_stream(
                    prompt="",
                    system=ADVISOR_SYSTEM,
                    max_tokens=700,
                    temp=0.72,
                ) if False else _stream_multi_turn(messages))
                elapsed = time.perf_counter() - start
                st.caption(f"{elapsed:.1f}s · {_ollama_model()}")

            history.append({"role": "assistant", "content": full or ""})
            st.session_state["advisor_history"] = history
            st.rerun()

        if history:
            if st.button("🗑️ Clear conversation", key="clear_chat"):
                st.session_state.pop("advisor_history", None)
                st.rerun()

    footer()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Packing List
# ══════════════════════════════════════════════════════════════════════════════
with tab_pack:
    banner(
        "Smart Packing List",
        "Describe your trip — get a fully categorised, AI-generated packing checklist.",
        accent="#f59e0b",
        tag="Packing Intelligence",
        bg=hero_bg,
    )

    # Input form
    with st.form("packing_form"):
        c1, c2 = st.columns(2)
        with c1:
            pk_dest = st.text_input("Destination", placeholder="e.g. Tokyo, Japan", key="pk_dest")
        with c2:
            pk_type = st.selectbox("Trip type", ["City break", "Beach holiday", "Hiking / Nature",
                                                  "Business trip", "Road trip", "Ski / Winter",
                                                  "Backpacking", "Cruise", "Family with kids"],
                                   key="pk_type")
        c3, c4, c5 = st.columns(3)
        with c3:
            pk_days = st.number_input("Duration (days)", min_value=1, max_value=90, value=7, key="pk_days")
        with c4:
            pk_season = st.selectbox("Season", ["Summer", "Spring", "Autumn", "Winter"], key="pk_season")
        with c5:
            pk_climate = st.selectbox("Climate", ["Temperate", "Hot & humid", "Hot & dry",
                                                    "Cold", "Variable / unpredictable"], key="pk_climate")
        pk_extras = st.text_input(
            "Special requirements (optional)",
            placeholder="e.g. formal dinner, photography gear, baby items",
            key="pk_extras",
        )
        pk_submit = st.form_submit_button("Generate Packing List →", use_container_width=True, type="primary")

    if pk_submit:
        if not pk_dest:
            st.warning("Please enter a destination.")
        elif not AI_ON:
            st.warning("AI required for packing list generation. Set OLLAMA_BASE_URL in secrets.")
        else:
            prompt = f"""Create a comprehensive, categorised packing list for this trip:

Destination: {pk_dest}
Trip type: {pk_type}
Duration: {pk_days} days
Season: {pk_season}
Climate: {pk_climate}
Special requirements: {pk_extras or 'none'}

Return ONLY a structured list in this exact format:
## Documents & Money
- Passport / ID
- Travel insurance documents
[etc]

## Clothing
- [items]

## Toiletries & Health
- [items]

## Tech & Gadgets
- [items]

## Medicines & First Aid
- [items]

## Bags & Accessories
- [items]

## Activity-specific
- [items specific to {pk_type} and {pk_dest}]

## Tips
- [3 specific packing tips for {pk_dest} in {pk_season}]

Be specific to this trip. Adjust quantities for {pk_days} days. Include items unique to {pk_dest} or {pk_type}."""

            system = f"You are a meticulous travel packer with expert knowledge of {pk_dest} and {pk_type.lower()} travel. Generate practical, specific packing lists."

            start = time.perf_counter()
            status = st.status("⚡ Generating packing list...", expanded=True)
            with status:
                full = st.write_stream(_stream(prompt, system=system, max_tokens=900, temp=0.65))
                elapsed = time.perf_counter() - start
                st.caption(f"Generated in {elapsed:.1f}s · Model: {_ollama_model()}")
            status.update(label=f"✅ Done · {elapsed:.1f}s", state="complete", expanded=False)
            full = full or ""

            if full and not full.startswith("⚠️"):
                # Parse into categories
                categories = {}
                current_cat = None
                for line in full.split("\n"):
                    line = line.strip()
                    if line.startswith("## "):
                        current_cat = line[3:].strip()
                        categories[current_cat] = []
                    elif line.startswith("- ") and current_cat:
                        categories[current_cat].append(line[2:].strip())

                st.session_state["packing_list"] = {
                    "destination": pk_dest,
                    "trip_type":   pk_type,
                    "duration":    pk_days,
                    "categories":  categories,
                    "raw":         full,
                }
                # Init checked state
                checked = {}
                for cat, items in categories.items():
                    for item in items:
                        checked[f"{cat}::{item}"] = False
                st.session_state["packing_checked"] = checked
                st.rerun()
            elif full:
                st.warning(full)

    pack = st.session_state.get("packing_list")
    if pack:
        categories = pack.get("categories", {})
        checked    = st.session_state.get("packing_checked", {})

        total_items   = sum(len(v) for v in categories.values())
        packed_items  = sum(1 for v in checked.values() if v)
        pct           = int(packed_items / total_items * 100) if total_items else 0

        sec("Packing Progress", "🎒")

        kc1, kc2, kc3 = st.columns(3)
        with kc1: kpi("🎒", "Total items",  str(total_items), color="#f59e0b")
        with kc2: kpi("✅", "Packed",       str(packed_items), color="#22c55e")
        with kc3: kpi("📊", "Progress",     f"{pct}%", color="#0ea5e9")

        st.markdown(f"""
        <div style="background:#0a1020;border-radius:6px;overflow:hidden;height:8px;margin:12px 0">
            <div class="pack-progress-bar" style="width:{pct}%;height:100%"></div>
        </div>""", unsafe_allow_html=True)

        # Trip meta
        st.markdown(f"""
        <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px">
            <span style="background:#0a1420;border:1px solid #1e2d42;border-radius:20px;
                         padding:4px 12px;color:#94a3b8;font-size:0.78rem">📍 {pack['destination']}</span>
            <span style="background:#0a1420;border:1px solid #1e2d42;border-radius:20px;
                         padding:4px 12px;color:#94a3b8;font-size:0.78rem">🏷️ {pack['trip_type']}</span>
            <span style="background:#0a1420;border:1px solid #1e2d42;border-radius:20px;
                         padding:4px 12px;color:#94a3b8;font-size:0.78rem">📅 {pack['duration']} days</span>
        </div>""", unsafe_allow_html=True)

        # Categories with checkboxes
        for cat, items in categories.items():
            if not items:
                continue
            cat_packed = sum(1 for item in items if checked.get(f"{cat}::{item}", False))
            cat_total  = len(items)
            sec(f"{cat}  ({cat_packed}/{cat_total})", "")

            cols_per_row = 2
            for i in range(0, len(items), cols_per_row):
                row_items = items[i:i + cols_per_row]
                row_cols  = st.columns(cols_per_row)
                for col, item in zip(row_cols, row_items):
                    key = f"{cat}::{item}"
                    with col:
                        val = st.checkbox(item, value=checked.get(key, False), key=f"pack_{key}")
                        if val != checked.get(key, False):
                            checked[key] = val
                            st.session_state["packing_checked"] = checked
                            st.rerun()

        # Export
        sec("Export", "⬇️")
        exp_col1, exp_col2 = st.columns(2)
        with exp_col1:
            export_text = f"Packing List — {pack['destination']} ({pack['trip_type']}, {pack['duration']} days)\n\n"
            for cat, items in categories.items():
                if items:
                    export_text += f"\n{cat}\n"
                    for item in items:
                        done = "✓" if checked.get(f"{cat}::{item}") else "○"
                        export_text += f"  [{done}] {item}\n"
            st.download_button(
                "⬇️ Download checklist",
                data=export_text,
                file_name=f"packing_{pack['destination'].replace(' ', '_')}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with exp_col2:
            if st.button("🗑️ Clear packing list", use_container_width=True, key="clear_pack"):
                st.session_state.pop("packing_list", None)
                st.session_state.pop("packing_checked", None)
                st.rerun()

    footer()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — About
# ══════════════════════════════════════════════════════════════════════════════
with tab_about:
    st.markdown(f"""
    <div style="border-radius:24px;overflow:hidden;position:relative;height:280px;
                background-image:{overview_bg};background-size:cover;background-position:center;
                border:1px solid #1a2e4a;margin-bottom:32px">
        <div style="position:absolute;inset:0;
                    background:linear-gradient(135deg,rgba(7,9,15,0.92) 0%,rgba(7,9,15,0.6) 100%)"></div>
        <div style="position:relative;z-index:1;padding:48px;height:100%;
                    display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center">
            <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;
                        letter-spacing:0.2em;color:#0ea5e9;margin-bottom:12px">Portfolio Project</div>
            <div style="font-size:2.5rem;font-weight:900;color:#f1f5f9;line-height:1">Journey Planner</div>
            <div style="color:#64748b;margin-top:12px;max-width:540px;line-height:1.7;font-size:0.88rem">
                Single and multi-stop route optimiser powered by Google Maps APIs. Compare transport modes,
                optimise waypoint order, get AI travel advice, and generate smart packing checklists.
                No login. No data stored.
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    ca, cb = st.columns(2)
    with ca:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#0c1628,#0f1e38);border:1px solid #1a2e4a;
                    border-radius:20px;padding:24px;margin-bottom:16px">
            <div style="font-weight:800;color:#f1f5f9;font-size:1rem;margin-bottom:16px">🗺️ Features</div>
            <div style="color:#64748b;line-height:2.2;font-size:0.88rem">
                🚦 <strong style="color:#94a3b8">Route Planner</strong> — Car, train, bus & flight comparison<br>
                🔀 <strong style="color:#94a3b8">Multi-Stop</strong> — Greedy nearest-neighbour optimisation<br>
                🤖 <strong style="color:#94a3b8">AI Advisor</strong> — Streaming travel intelligence chat<br>
                🎒 <strong style="color:#94a3b8">Packing List</strong> — AI-generated, interactive checklist<br>
                🌿 <strong style="color:#94a3b8">CO₂ Tracker</strong> — Carbon footprint per transport mode
            </div>
        </div>
        <div style="background:linear-gradient(135deg,#0c1628,#0f1e38);border:1px solid #1a2e4a;
                    border-radius:20px;padding:24px">
            <div style="font-weight:800;color:#f1f5f9;font-size:1rem;margin-bottom:16px">🔑 APIs Used</div>
            <div style="color:#64748b;line-height:2;font-size:0.88rem">
                🗺️ <strong style="color:#94a3b8">Google Geocoding</strong> — Location → lat/lon<br>
                📏 <strong style="color:#94a3b8">Google Distance Matrix</strong> — Driving distances & times<br>
                📐 <strong style="color:#94a3b8">Haversine formula</strong> — Fallback great-circle distance<br>
                🤖 <strong style="color:#94a3b8">Ollama</strong> — Local LLM via Cloudflare Tunnel<br>
                🔒 <strong style="color:#94a3b8">No login</strong> — All data lives in your browser session
            </div>
        </div>
        """, unsafe_allow_html=True)

    with cb:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#0c1628,#0f1e38);border:1px solid #1a2e4a;
                    border-radius:20px;padding:24px;margin-bottom:16px">
            <div style="font-weight:800;color:#f1f5f9;font-size:1rem;margin-bottom:16px">👨‍💻 Built by</div>
            <div style="font-size:1.1rem;font-weight:700;color:#e2e8f0">Sameer Bhalerao</div>
            <div style="color:#4b5a7a;font-size:0.85rem;margin-top:2px">Senior Analytics & AI Product Leader · Amazon L6</div>
            <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap">
                <a href="https://www.linkedin.com/in/sameervb" target="_blank"
                   style="background:#0d1e30;border:1px solid #1a3050;border-radius:8px;padding:6px 14px;
                          color:#60a5fa;font-size:0.8rem;text-decoration:none">LinkedIn</a>
                <a href="https://github.com/sameervb" target="_blank"
                   style="background:#0d1e30;border:1px solid #1a3050;border-radius:8px;padding:6px 14px;
                          color:#94a3b8;font-size:0.8rem;text-decoration:none">GitHub</a>
                <a href="https://soulspark.me" target="_blank"
                   style="background:#0c1a2a;border:1px solid #1a2d42;border-radius:8px;padding:6px 14px;
                          color:#0ea5e9;font-size:0.8rem;text-decoration:none">Soul Spark</a>
            </div>
            <div style="color:#334155;font-size:0.82rem;line-height:1.7;margin-top:16px">
                This is app #3 of 10 standalone public apps extracted from
                <a href="https://soulspark.me" style="color:#0ea5e9">Soul Spark</a> — a local-first
                personal intelligence platform built end-to-end in 8 weeks.
            </div>
        </div>
        <div style="background:linear-gradient(135deg,#0c1628,#0f1e38);border:1px solid #1a2e4a;
                    border-radius:20px;padding:24px">
            <div style="font-weight:800;color:#f1f5f9;font-size:1rem;margin-bottom:16px">🛠️ Tech Stack</div>
            <div style="display:flex;flex-wrap:wrap;gap:8px">
        """, unsafe_allow_html=True)
        for badge in ["Python 3.14", "Streamlit", "Google Maps API",
                      "Plotly", "Pandas", "Ollama (LLaMA 3.1)",
                      "Cloudflare Tunnel", "Streamlit Community Cloud"]:
            st.markdown(
                f'<span style="background:#0a1420;border:1px solid #1e3050;border-radius:20px;'
                f'padding:5px 12px;color:#94a3b8;font-size:0.75rem">{badge}</span>',
                unsafe_allow_html=True,
            )
        st.markdown("</div></div>", unsafe_allow_html=True)

    footer()
