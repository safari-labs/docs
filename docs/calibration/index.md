# NDVI/NDRE Documentation

This documentation covers the full procedure for determining vegetation indices using a Sony A7S II converted to full-spectrum photography with a Hoya A25 red filter.

The methodology is based on Patón (2020), *Normalized Difference Vegetation Index Determination in Urban Areas by Full-Spectrum Photography*, Ecologies 1, 22–35, adapted for the Sony A7S II.

## Overview

Rather than relying on expensive multispectral cameras, this procedure converts a consumer camera into a full-spectrum device capable of capturing red and near-infrared radiation simultaneously. A key feature of this methodology is that the spectral response of the specific camera body is characterized empirically from the calibration data itself, rather than assumed from manufacturer specifications.

Depending on the results of the wavelength characterization, the procedure produces either:

- **NDVI** (Normalized Difference Vegetation Index) — standard index using red and NIR bands
- **NDRE** (Normalized Difference Red Edge) — more sensitive index using red-edge and NIR bands, preferred for detecting early plant stress and canopy nitrogen content

## Equipment

- Sony A7S II (full-spectrum converted)
- Hoya A25 red filter
- Macbeth X-Rite ColorChecker (11" × 8.25")
- Computer running R, ImageJ, DCRAW, and ImageMagick

## Documentation Structure

- **Camera Setup** — conversion and base settings
- **Calibration Procedure** — step-by-step calibration workflow
- **Index Selection** — wavelength characterization and index decision logic
