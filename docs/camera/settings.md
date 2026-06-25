# Camera Settings

## Base Settings

| Parameter | Value | Reason |
|---|---|---|
| ISO | 100 | Base ISO minimises noise and overexposure risk |
| Format | ARW (RAW uncompressed) | Preserves linear sensor data without post-processing |
| Mode | Manual | Metering system unreliable after hot mirror removal |
| White balance | Custom (CWB) | Set before each session — see [White Balance](../calibration/cwb.md) |

## Filter

Mount the **Hoya A25** red filter on the lens. This filter transmits approximately 95% of red and NIR wavelengths while blocking UV, blue, and green. With the hot mirror removed and the A25 filter in place, the three sensor channels capture:

| Channel | Captures | Role |
|---|---|---|
| Red | ~600–700 nm | Red reflectance (R) |
| Green | NIR1 — exact wavelength determined by calibration | Red-edge or NIR1 |
| Blue | NIR2 — exact wavelength determined by calibration | NIR2 if reliable |

!!! warning
    The exact wavelengths captured by the green and blue channels depend on your specific camera body and cannot be assumed from manufacturer specifications. The [Wavelength Characterization](../calibration/wavelengths.md) step determines these empirically from your calibration data.

## Exposure Range

Due to hot mirror removal, the sensor receives significantly more light than normal. Finding the correct exposure requires initial testing. The following ranges have been found to work as a starting point:

| Parameter | Range |
|---|---|
| Exposure (Ev) | 6.1–14.3 |
| F-stop | f/4–f/16 |
| Shutter speed | 1/500s–1/6s |

Apertures below f/4 tend to overexpose. Shutter speeds faster than 1/500s do not allow enough infrared radiation. Always verify exposure using the histogram — see [White Balance](../calibration/cwb.md) for histogram checking procedure.
