#!/usr/bin/env python3
import json, sys, numpy as np
import urllib.request

url = "http://localhost:5050/api/link_budget?tx=dipole_half_wave&rx=yagi&gs_lat=48.5678&gs_lon=-81.3655&gs_alt=285.8"
with urllib.request.urlopen(url) as resp:
    d = json.load(resp)

# Extract data
lats = np.array([p['lat'] for p in d])
lons = np.array([p['lon'] for p in d])
alts = np.array([p['alt'] for p in d])

# Calculate velocity
dlat = np.diff(lats, prepend=lats[0])
dlon = np.diff(lons, prepend=lons[0])
dalt = np.diff(alts, prepend=alts[0])

LAT_TO_M = 111320
velocity_ns = dlat * LAT_TO_M
velocity_ew = dlon * LAT_TO_M * np.cos(np.radians(lats))
velocity_up = dalt

# Calculate acceleration
accel_ns = np.diff(velocity_ns, prepend=velocity_ns[0])
accel_ew = np.diff(velocity_ew, prepend=velocity_ew[0])
accel_up = np.diff(velocity_up, prepend=velocity_up[0])

total_accel = np.sqrt(accel_ns**2 + accel_ew**2 + accel_up**2)

print(f"Max accel: {total_accel.max():.2f} m/s²")
print(f"Positions:\n  Lat range: {lats.min():.5f} to {lats.max():.5f}")
print(f"  Lon range: {lons.min():.5f} to {lons.max():.5f}")
print(f"  Alt range: {alts.min():.1f} to {alts.max():.1f} m")
print(f"  dlat max: {np.abs(dlat).max():.6f}, dlon max: {np.abs(dlon).max():.6f}")
print(f"Velocity (m/s): NS max={velocity_ns.max():.2f}, EW max={velocity_ew.max():.2f}, U max={velocity_up.max():.2f}")
