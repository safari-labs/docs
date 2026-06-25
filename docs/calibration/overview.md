# Calibration Overview

## Purpose

The calibration procedure establishes the mathematical relationship between the brightness values recorded by the camera sensor and the true reflectance values of surfaces in red and near-infrared wavelengths. These relationships are expressed as exponential regression models of the form:

```
Reflectance = a × exp(b × Brightness)
```

One model is fitted for each reliable channel. The coefficients `a` and `b` are specific to this camera body and must be derived from your own calibration data — the coefficients reported in Patón (2020) apply only to the Nikon D50 and cannot be reused.

## Additional Purpose: Wavelength Characterization

Because Sony does not publish the spectral sensitivity curve for the A7S II sensor, this calibration procedure also characterizes which wavelengths each channel is capturing empirically. This is done by correlating measured channel brightnesses against the known reflectance values of the ColorChecker panels at each candidate wavelength. The result determines which vegetation index is most appropriate for this camera.

## Steps

1. [White Balance](cwb.md) — custom white balance before each session
2. [ColorChecker Photography](colorchecker.md) — collecting calibration photos
3. [RAW Conversion](colorchecker.md#raw-conversion) — converting ARW files to TIFF
4. [Histogram Equalization](colorchecker.md#histogram-equalization) — normalizing exposure
5. [ImageJ Measurement](colorchecker.md#imagej-measurement) — measuring panel brightnesses
6. [Wavelength Characterization](wavelengths.md) — determining channel wavelengths
7. [Regression Models](regression.md) — fitting reflectance models
8. [Validation](validation.md) — hierarchical partitioning validation

## Software Requirements

| Software | Purpose | Source |
|---|---|---|
| DCRAW 9.20 | ARW to TIFF conversion | dcraw.sourceforge.net |
| ImageMagick 7+ | Histogram equalization | imagemagick.org |
| ImageJ 1.8.0+ | Brightness measurement | imagej.nih.gov |
| R 4.0+ | Regression and validation | r-project.org |
| R package: `hier.part` | Hierarchical partitioning | CRAN |
