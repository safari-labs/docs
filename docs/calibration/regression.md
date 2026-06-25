# Regression Models

## Purpose

Three exponential regression models are fitted to relate the brightness values measured by the camera sensor to the true reflectance values of the ColorChecker panels. These models are used in the ImageJ script to convert raw channel brightness in field photographs into reflectance values, from which the vegetation index is calculated.

The models take the form:

```
Reflectance = a × exp(b × Brightness)
```

## R Code

```r
# Load data
your_data <- read.csv("imagej_measurements.csv")

# Merge with X-Rite reflectance values
xrite <- read.csv("xrite_nir_reflectances.csv")
your_data <- merge(your_data, xrite, by = "panel_id")

# Red channel → R reflectance
model_R <- nls(reflectance_R ~ a * exp(b * R_brightness),
               data = your_data,
               start = list(a = 0.02, b = 0.00005))

# Green channel → NIR1 reflectance
model_NIR1 <- nls(reflectance_NIR1 ~ a * exp(b * G_brightness),
                  data = your_data,
                  start = list(a = 0.03, b = 0.00005))

# Blue channel → NIR2 reflectance
# Include regardless — reliability determined by wavelength characterization
model_NIR2 <- nls(reflectance_NIR2 ~ a * exp(b * B_brightness),
                  data = your_data,
                  start = list(a = 0.05, b = 0.00005))

summary(model_R)
summary(model_NIR1)
summary(model_NIR2)
```

## Extracting Coefficients

```r
# Extract a and b coefficients for use in ImageJ script
coef_R    <- coef(model_R)
coef_NIR1 <- coef(model_NIR1)
coef_NIR2 <- coef(model_NIR2)

cat("Red channel:   a =", coef_R["a"],    "  b =", coef_R["b"],    "\n")
cat("NIR1 channel:  a =", coef_NIR1["a"], "  b =", coef_NIR1["b"], "\n")
cat("NIR2 channel:  a =", coef_NIR2["a"], "  b =", coef_NIR2["b"], "\n")
```

Record these coefficients — they are entered into the ImageJ script in the [Index Selection](index-selection.md) step.

## Acceptance Criteria

| Model | Minimum R² | Notes |
|---|---|---|
| Red (R) | 0.95 | Should be cleanly fitted — red channel is least ambiguous |
| NIR1 (G) | 0.95 | Should be comparably clean |
| NIR2 (B) | 0.85 | Lower threshold reflects greater uncertainty in blue channel |

If R or NIR1 fall below their thresholds, the most common cause is inconsistent CWB between sessions. Identify and reshoot the sessions where CWB was not properly set and refit the models.

If NIR2 falls below 0.85, treat the blue channel as unreliable regardless of the wavelength characterization result and fall back to standard NDVI using R and NIR1 only.

!!! warning
    Do not use the coefficients from Patón (2020). Those values apply only to the Nikon D50 and will produce incorrect reflectance estimates on the A7S II.
