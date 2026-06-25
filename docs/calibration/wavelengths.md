# Wavelength Characterization

## Purpose

Because Sony does not publish the spectral sensitivity curve for the A7S II sensor, the dominant wavelength captured by each channel is determined empirically from the calibration data. This is done by correlating the measured channel brightnesses across the 24 ColorChecker panels against the known panel reflectances at each candidate wavelength. The wavelength producing the highest correlation for a given channel is its dominant wavelength.

This step also determines the reliability of the blue channel for NIR2 measurement, and from that decides which vegetation index — NDVI or NDRE — is most appropriate for this camera body.

## R Code

```r
library(dplyr)

# Load X-Rite reflectance data (columns named nm_600, nm_610, ... nm_950)
reflectance_table <- read.csv("xrite_nir_reflectances.csv")

# Load ImageJ brightness measurements
brightness <- read.csv("imagej_measurements.csv")

# Candidate wavelengths to test
wavelengths <- seq(600, 950, by = 10)

# Correlate each channel's brightness against known reflectance at each wavelength
characterize_channel <- function(channel_brightness, reflectance_table) {
  correlations <- sapply(wavelengths, function(wl) {
    col_name <- paste0("nm_", wl)
    cor(channel_brightness, reflectance_table[[col_name]])
  })
  data.frame(wavelength = wavelengths, correlation = correlations)
}

red_char   <- characterize_channel(brightness$R_brightness, reflectance_table)
green_char <- characterize_channel(brightness$G_brightness, reflectance_table)
blue_char  <- characterize_channel(brightness$B_brightness, reflectance_table)

# Extract peak wavelengths and blue channel reliability
red_peak_wl   <- red_char$wavelength[which.max(red_char$correlation)]
green_peak_wl <- green_char$wavelength[which.max(green_char$correlation)]
blue_peak_wl  <- blue_char$wavelength[which.max(blue_char$correlation)]
blue_max_cor  <- max(blue_char$correlation)

cat("Red channel dominant wavelength:  ", red_peak_wl, "nm\n")
cat("Green channel dominant wavelength:", green_peak_wl, "nm\n")
cat("Blue channel dominant wavelength: ", blue_peak_wl, "nm\n")
cat("Blue channel peak correlation:    ", round(blue_max_cor, 3), "\n\n")

# Determine index recommendation
blue_reliable <- blue_max_cor >= 0.85 & blue_peak_wl >= 800
green_rededge <- green_peak_wl >= 700 & green_peak_wl <= 750

if (blue_reliable & green_rededge) {
  cat("RESULT: Green channel = red-edge (~", green_peak_wl, "nm)\n")
  cat("        Blue channel  = NIR      (~", blue_peak_wl, "nm)\n")
  cat("RECOMMENDED INDEX: NDRE = (NIR2 - NIR1) / (NIR2 + NIR1)\n")
} else if (blue_reliable & !green_rededge) {
  cat("RESULT: Green channel = NIR1 (~", green_peak_wl, "nm)\n")
  cat("        Blue channel  = NIR2 (~", blue_peak_wl, "nm)\n")
  cat("RECOMMENDED INDEX: NDVI = (NIR1 - R) / (NIR1 + R)\n")
  cat("        Green channel too deep for red-edge use\n")
} else {
  cat("RESULT: Green channel = NIR1 (~", green_peak_wl, "nm)\n")
  cat("        Blue channel unreliable — exclude from analysis\n")
  cat("RECOMMENDED INDEX: NDVI = (NIR1 - R) / (NIR1 + R)\n")
}
```

## Interpreting the Output

| Green peak | Blue reliable | Blue peak | Recommended index |
|---|---|---|---|
| 700–750 nm | Yes (≥0.85) | ≥800 nm | NDRE — green = red-edge, blue = NIR |
| >750 nm | Yes (≥0.85) | ≥800 nm | NDVI — green = NIR, blue = NIR2 |
| Any | No (<0.85) | Any | NDVI — red and green channels only |

## Notes

This characterization identifies the dominant wavelength per channel but does not resolve the full bandwidth. For NDVI and NDRE calculation this is sufficient — what matters is that red is capturing the chlorophyll absorption region (~650–680 nm) and that the NIR or red-edge channel is clearly separated from it. Proceed to [Regression Models](regression.md) regardless of the outcome — the characterization determines how you interpret and use the models, not whether you fit them.
