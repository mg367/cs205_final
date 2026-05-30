"""
server_monitor.py — Run this on the Linux machine you want to watch.

Start: uvicorn server_monitor:app --host 0.0.0.0 --port 8000
Visit: http://<your-lan-ip>:8000/docs  to test the API in a browser.

net_connections() requires root for full visibility.
If you see active_connections = -1, re-run with: sudo uvicorn server_monitor:app ...
"""

from fastapi import FastAPI
import psutil
import time

app = FastAPI(title="Cyber Monitor API")

# Seed the baseline so the first delta isn't garbage
_last_net = psutil.net_io_counters()
_last_time = time.time()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def get_metrics():
    global _last_net, _last_time

    now = time.time()
    elapsed = now - _last_time or 1  # guard against zero division on very fast polls

    net_now = psutil.net_io_counters()
    sent_rate = (net_now.bytes_sent - _last_net.bytes_sent) / elapsed
    recv_rate = (net_now.bytes_recv - _last_net.bytes_recv) / elapsed

    _last_net = net_now
    _last_time = now

    try:
        connections = len(psutil.net_connections())
    except psutil.AccessDenied:
        connections = -1  # -1 signals "need root" to the dashboard

    disk = psutil.disk_usage("/")
    load_1m, load_5m, _ = psutil.getloadavg()
    mem = psutil.virtual_memory()

    return {
        "timestamp": now,
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": mem.percent,
        "memory_used_gb": round(mem.used / 1_073_741_824, 2),
        "memory_total_gb": round(mem.total / 1_073_741_824, 2),
        "bytes_sent_per_sec": round(sent_rate, 2),
        "bytes_recv_per_sec": round(recv_rate, 2),
        "bytes_sent_total": net_now.bytes_sent,
        "bytes_recv_total": net_now.bytes_recv,
        "active_connections": connections,
        "load_avg_1m": load_1m,
        "load_avg_5m": load_5m,
        "disk_used_percent": disk.percent,
        "disk_used_gb": round(disk.used / 1_073_741_824, 2),
        "disk_total_gb": round(disk.total / 1_073_741_824, 2),
    }
