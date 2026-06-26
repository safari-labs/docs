"""
Antenna Registry — Pluggable antenna pattern system.

To add a new antenna type:
  1. Write a pattern function: (theta_deg, phi_deg, gain_dbi) → gain_db (numpy arrays)
  2. Call AntennaRegistry.register(key, definition)

No subclassing required — just register a callable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional

import numpy as np

# Type alias for pattern functions
PatternFn = Callable[[np.ndarray, np.ndarray, float], np.ndarray]


@dataclass(frozen=True)
class AntennaDefinition:
    """Immutable descriptor for an antenna type."""

    name: str
    gain_dbi: float
    pattern_fn: PatternFn
    color: str = "#00d4ff"
    description: str = ""
    use_case: str = ""
    beamwidth_3db: float = 80.0


# ── Built-in pattern functions ──────────────────────────────────────

def dipole_pattern(th: np.ndarray, ph: np.ndarray, g: float) -> np.ndarray:
    t = np.radians(np.asarray(th, float))
    p = np.clip(np.sin(t) ** 2, 1e-12, 1)
    return np.clip(10 * np.log10(p) + g, -200, None)


def yagi_pattern(
    th: np.ndarray, ph: np.ndarray, g: float, bw: float = 30,
) -> np.ndarray:
    t = np.radians(np.asarray(th, float))
    main = np.clip(np.abs(np.cos(t)) ** (2 * np.pi / bw), 0.05, 1)
    sll = np.clip(np.abs(np.cos(t * 3)) ** 2, 1e-12, 1e6)
    p = np.max(np.stack([main, sll * 0.05], axis=0), axis=0)
    mx = np.clip(p, 1e-12, 1e6)
    return np.clip(10 * np.log10(mx) + g, -200, None)


def patch_pattern(th: np.ndarray, ph: np.ndarray, g: float) -> np.ndarray:
    th_arr = np.asarray(th, float)
    t = np.radians(th_arr)
    p = np.where(th_arr < 90, np.cos(t) ** 2, 1e-12)
    return np.clip(10 * np.log10(np.clip(p, 1e-12, None)) + g, -200, None)


def helix_pattern(th: np.ndarray, ph: np.ndarray, g: float) -> np.ndarray:
    t = np.radians(np.asarray(th, float))
    n = 8
    sinc_arg = np.clip(n * np.cos(t) / np.pi, -100, 100)
    p = np.clip(np.abs(np.sinc(sinc_arg)) * np.cos(t / 2) ** 2, 1e-12, 1e6)
    mx = np.max(np.stack([p], axis=0), axis=0)
    return np.clip(10 * np.log10(np.clip(mx, 1e-12, None)) + g, -200, None)


def omni_pattern(th: np.ndarray, ph: np.ndarray, g: float) -> np.ndarray:
    return np.full_like(np.asarray(th, float), g)


# ── AntennaRegistry (class-level dict, no instances needed) ─────────

class AntennaRegistry:
    """
    Central registry for antenna definitions.
    Thread-safe for reads (dict lookup). Writes happen at startup only.
    """

    _antennas: Dict[str, AntennaDefinition] = {}
    _custom_antennas: Dict[str, AntennaDefinition] = {}

    @classmethod
    def register(cls, key: str, definition: AntennaDefinition) -> None:
        cls._antennas[key] = definition

    @classmethod
    def register_custom(cls, key: str, definition: AntennaDefinition) -> None:
        cls._custom_antennas[key] = definition

    @classmethod
    def unregister_custom(cls, key: str) -> None:
        cls._custom_antennas.pop(key, None)

    @classmethod
    def get(cls, key: str) -> Optional[AntennaDefinition]:
        return cls._antennas.get(key) or cls._custom_antennas.get(key)

    @classmethod
    def is_valid(cls, key: str) -> bool:
        return key in cls._antennas or key in cls._custom_antennas

    @classmethod
    def all_configs(cls) -> Dict[str, dict]:
        result = {}
        for k, d in {**cls._antennas, **cls._custom_antennas}.items():
            result[k] = {
                "name": d.name,
                "gain_dbi": d.gain_dbi,
                "color": d.color,
                "description": d.description,
                "use_case": d.use_case,
            }
        return result

    @classmethod
    def get_custom_antennas(cls) -> Dict[str, dict]:
        return {
            k: {
                "name": d.name,
                "gain_dbi": d.gain_dbi,
                "color": d.color,
                "description": d.description,
            }
            for k, d in cls._custom_antennas.items()
        }

    @classmethod
    def compute_gain(
        cls, key: str, elevation: np.ndarray, azimuth: np.ndarray,
    ) -> np.ndarray:
        """Compute gain (dBi) for the given look angles."""
        defn = cls.get(key)
        if defn is None:
            defn = cls._antennas.get("dipole_half_wave")
        theta = np.clip(90 - np.asarray(elevation, float), 0, 180)
        return np.asarray(
            defn.pattern_fn(theta, np.asarray(azimuth, float), defn.gain_dbi),
            float,
        )

    @classmethod
    def compute_gain_pattern(
        cls, key: str, theta: np.ndarray, phi: np.ndarray,
    ) -> np.ndarray:
        """Compute gain pattern for spherical coordinates (for visualization)."""
        defn = cls.get(key)
        if defn is None:
            defn = cls._antennas.get("dipole_half_wave")
        return defn.pattern_fn(theta, phi, defn.gain_dbi)

    @classmethod
    def get_beamwidth(cls, key: str) -> float:
        defn = cls.get(key)
        if defn:
            return defn.beamwidth_3db
        return 80.0


# ── Register built-in antennas at import time ──────────────────────

def _register_builtins() -> None:
    builtins = [
        ("dipole_half_wave", AntennaDefinition(
            name="Dipôle λ/2",
            gain_dbi=2.2,
            pattern_fn=dipole_pattern,
            color="#00d4ff",
            description="Pattern torique, omnidirectionnel H",
            use_case="Embarquée ballon",
            beamwidth_3db=120.0,
        )),
        ("yagi", AntennaDefinition(
            name="Yagi-Uda",
            gain_dbi=13.0,
            pattern_fn=yagi_pattern,
            color="#ff6b35",
            description="Lobe principal étroit, très directif",
            use_case="Station sol pointée ballon",
            beamwidth_3db=30.0,
        )),
        ("patch", AntennaDefinition(
            name="Patch",
            gain_dbi=7.0,
            pattern_fn=patch_pattern,
            color="#a8ff3e",
            description="Hémisphérique, polarisation linéaire",
            use_case="Embarquée — couverture ciel",
            beamwidth_3db=60.0,
        )),
        ("helix", AntennaDefinition(
            name="Hélice axiale",
            gain_dbi=10.0,
            pattern_fn=helix_pattern,
            color="#ff3ea8",
            description="Mode axial, polarisation circulaire",
            use_case="Embarquée — tolérance roulis",
            beamwidth_3db=40.0,
        )),
        ("omni", AntennaDefinition(
            name="Omni",
            gain_dbi=2.2,
            pattern_fn=omni_pattern,
            color="#ffe03e",
            description="Couverture sphérique uniforme",
            use_case="Référence / sol non-orienté",
            beamwidth_3db=360.0,
        )),
    ]
    for key, defn in builtins:
        AntennaRegistry.register(key, defn)


_register_builtins()
