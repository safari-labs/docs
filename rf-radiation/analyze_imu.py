#!/usr/bin/env python3
"""Analyser les vraies vitesses et accélérations du ballon"""
import json, urllib.request, numpy as np
from datetime import datetime

d = json.load(urllib.request.urlopen('http://localhost:5050/api/link_budget?tx=dipole_half_wave&rx=yagi&gs_lat=48.5678&gs_lon=-81.3655&gs_alt=285.8'))

# Parse ISO 8601 timestamps
timestamps = np.array([datetime.fromisoformat(p['timestamp'].replace('Z', '+00:00')).timestamp() for p in d])
lats = np.array([p['lat'] for p in d])
lons = np.array([p['lon'] for p in d])
alts = np.array([p['alt'] for p in d])

print(f"Timestamps: {timestamps[0]:.1f} to {timestamps[-1]:.1f}, diff={timestamps[-1]-timestamps[0]:.1f} s")
print(f"Temps entre points: min={np.diff(timestamps).min():.2f}, max={np.diff(timestamps).max():.2f}, mean={np.diff(timestamps).mean():.2f} s")

# Calculer les VRAIES vitesses
dt = np.diff(timestamps, prepend=timestamps[0])
dt[0] = dt[1] if len(dt) > 1 else 1

dlat = np.diff(lats, prepend=lats[0])
dlon = np.diff(lons, prepend=lons[0])
dalt = np.diff(alts, prepend=alts[0])

LAT_TO_M = 111320
v_ns = dlat * LAT_TO_M / dt
v_ew = dlon * LAT_TO_M * np.cos(np.radians(lats)) / dt
v_up = dalt / dt

speed = np.sqrt(v_ns**2 + v_ew**2 + v_up**2)

print(f"\nVitesses (m/s):")
print(f"  Horizontal: {np.sqrt((dlat*LAT_TO_M/dt)**2 + (dlon*LAT_TO_M/dt)**2).mean():.1f} m/s mean")
print(f"  Vertical: {v_up.mean():.1f} m/s mean, max={v_up.max():.1f} m/s")
print(f"  Total: {speed.mean():.1f} m/s mean, max={speed.max():.1f} m/s")

# Calculer les accélérations
dv_ns = np.diff(v_ns, prepend=v_ns[0])
dv_ew = np.diff(v_ew, prepend=v_ew[0])
dv_up = np.diff(v_up, prepend=v_up[0])

a_ns = dv_ns / dt
a_ew = dv_ew / dt
a_up = dv_up / dt

accel = np.sqrt(a_ns**2 + a_ew**2 + a_up**2)

print(f"\nAccélérations (m/s²):")
print(f"  Max: {accel.max():.3f} m/s²")
print(f"  Mean: {accel.mean():.4f} m/s²")
print(f"  Std: {accel.std():.4f} m/s²")
