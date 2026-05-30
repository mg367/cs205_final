"""
local_dash.py — Run this on your desktop/laptop to watch the server.

Start: streamlit run local_dash.py
Then open http://localhost:8501 in your browser.

Set the Server URL in the sidebar to http://<server-lan-ip>:8000
"""

import time
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Cyber Monitor", layout="centered", page_icon="shield")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    server_url = st.text_input(
        "Server URL",
        value="http://localhost:8000",
        help="Change this to your server's LAN IP, e.g. http://192.168.1.42:8000",
    )
    refresh_rate = st.slider("Refresh every (seconds)", min_value=1, max_value=10, value=2)
    st.divider()
    st.subheader("Alert Thresholds")
    conn_threshold = st.number_input("Connections", min_value=10, value=100)
    cpu_threshold = st.number_input("CPU %", min_value=10, max_value=100, value=80)
    net_threshold = st.number_input("Outbound KB/s", min_value=10, value=5000)

# ── Session state for rolling history ────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []

# ── Title ─────────────────────────────────────────────────────────────────────
st.title("Cyber Monitor")

# ── Fetch ─────────────────────────────────────────────────────────────────────
try:
    resp = requests.get(f"{server_url}/metrics", timeout=3)
    resp.raise_for_status()
    d = resp.json()

    ts = datetime.fromtimestamp(d["timestamp"]).strftime("%H:%M:%S")

    # Rolling 60-sample history for charts
    st.session_state.history.append(
        {
            "time": ts,
            "CPU %": d["cpu_percent"],
            "Memory %": d["memory_percent"],
            "Recv KB/s": round(d["bytes_recv_per_sec"] / 1024, 2),
            "Sent KB/s": round(d["bytes_sent_per_sec"] / 1024, 2),
            "Connections": max(d["active_connections"], 0),
        }
    )
    if len(st.session_state.history) > 60:
        st.session_state.history.pop(0)

    # ── Alerts ────────────────────────────────────────────────────────────────
    alerts = []
    if d["active_connections"] > conn_threshold:
        alerts.append(f"High connection count: {d['active_connections']} (threshold {conn_threshold})")
    if d["cpu_percent"] > cpu_threshold:
        alerts.append(f"High CPU usage: {d['cpu_percent']}% (threshold {cpu_threshold}%)")
    if d["bytes_sent_per_sec"] / 1024 > net_threshold:
        alerts.append(
            f"High outbound traffic: {d['bytes_sent_per_sec']/1024:.0f} KB/s "
            f"(threshold {net_threshold} KB/s) — possible data exfiltration"
        )
    if d["disk_used_percent"] > 90:
        alerts.append(f"Low disk space: {d['disk_used_percent']}% used")

    for alert in alerts:
        st.warning(f"WARNING  {alert}")

    # ── Core metrics ──────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CPU", f"{d['cpu_percent']}%")
    c2.metric("Memory", f"{d['memory_percent']}%", f"{d['memory_used_gb']} / {d['memory_total_gb']} GB")
    c3.metric(
        "Connections",
        d["active_connections"] if d["active_connections"] >= 0 else "N/A",
        help="Run server as root for full visibility" if d["active_connections"] < 0 else None,
    )
    c4.metric("Disk Used", f"{d['disk_used_percent']}%", f"{d['disk_used_gb']} / {d['disk_total_gb']} GB")

    # ── Network ───────────────────────────────────────────────────────────────
    st.subheader("Network (KB/s)")
    n1, n2 = st.columns(2)
    n1.metric("Inbound", f"{d['bytes_recv_per_sec']/1024:.1f} KB/s")
    n2.metric("Outbound", f"{d['bytes_sent_per_sec']/1024:.1f} KB/s")

    # ── Load average (Linux only) ─────────────────────────────────────────────
    st.subheader("Load Average")
    l1, l2 = st.columns(2)
    l1.metric("1-minute", d["load_avg_1m"])
    l2.metric("5-minute", d["load_avg_5m"])

    # ── Charts ────────────────────────────────────────────────────────────────
    if len(st.session_state.history) > 1:
        df = pd.DataFrame(st.session_state.history).set_index("time")
        st.subheader("CPU & Memory History")
        st.line_chart(df[["CPU %", "Memory %"]])
        st.subheader("Network Traffic History (KB/s)")
        st.line_chart(df[["Recv KB/s", "Sent KB/s"]])
        st.subheader("Connection Count History")
        st.line_chart(df[["Connections"]])

    st.caption(f"Last updated: {ts}  |  Refreshing every {refresh_rate}s")

except requests.exceptions.ConnectionError:
    st.error(f"Cannot reach server at {server_url}. Is server_monitor.py running?")
    st.info("Start it with:  uvicorn server_monitor:app --host 0.0.0.0 --port 8000")
except requests.exceptions.Timeout:
    st.warning("Server did not respond within 3 seconds.")
except Exception as e:
    st.error(f"Unexpected error: {e}")

time.sleep(refresh_rate)
st.rerun()
