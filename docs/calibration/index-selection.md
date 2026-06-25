# Index Selection and ImageJ Scripts

## Decision Logic

The vegetation index used depends on the outcome of the [Wavelength Characterization](wavelengths.md) step and the R² values from the [Regression Models](regression.md) step. Use this table to determine which script to use:

| Green peak | Blue R² | Blue peak | Index | Channels |
|---|---|---|---|---|
| 700–750 nm | ≥0.85 | ≥800 nm | **NDRE** | Green = red-edge, Blue = NIR |
| >750 nm | ≥0.85 | ≥800 nm | **NDVI** | Red = R, Green = NIR |
| Any | <0.85 | Any | **NDVI** | Red = R, Green = NIR only |

## NDRE Script

Use when the green channel peak falls in the red-edge window (700–750 nm) and the blue channel is reliable.

NDRE = (NIR − RedEdge) / (NIR + RedEdge)

Replace `[a_R]`, `[b_R]`, `[a_NIR1]`, `[b_NIR1]`, `[a_NIR2]`, `[b_NIR2]` with your coefficients from the regression step.

```
run("32-bit");
saveAs("Tiff", "/tmp/test.tif");
run("Split Channels");

selectWindow("C3-test.tif");
run("Close");

// Red channel → R reflectance (retained for reference)
selectWindow("C1-test.tif");
run("Multiply...", "value=[b_R]");
run("Exp");
run("Multiply...", "value=[a_R]");
saveAs("Tiff", "/tmp/R.tif");

// Green channel → red-edge reflectance
selectWindow("C2-test.tif");
run("Multiply...", "value=[b_NIR1]");
run("Exp");
run("Multiply...", "value=[a_NIR1]");
saveAs("Tiff", "/tmp/RE.tif");

// Blue channel → NIR reflectance
selectWindow("C3-test.tif");
run("Multiply...", "value=[b_NIR2]");
run("Exp");
run("Multiply...", "value=[a_NIR2]");
saveAs("Tiff", "/tmp/NIR.tif");

// NDRE = (NIR - RE) / (NIR + RE)
imageCalculator("Subtract create 32-bit", "NIR.tif", "RE.tif");
saveAs("Tiff", "/tmp/N1.tif");
imageCalculator("Add create 32-bit", "NIR.tif", "RE.tif");
saveAs("Tiff", "/tmp/D1.tif");

selectWindow("R.tif");
close();
selectWindow("RE.tif");
close();
selectWindow("NIR.tif");
close();

imageCalculator("Divide create 32-bit", "N1.tif", "D1.tif");
selectWindow("Result of N1.tif");
run("NDVI_colors");
saveAs("Tiff", "/tmp/NDRE.tif");

selectWindow("D1.tif");
close();
selectWindow("N1.tif");
close();
```

## NDVI Script

Use when the green channel peak is above 750 nm, or when the blue channel is unreliable.

NDVI = (NIR − R) / (NIR + R)

Replace `[a_R]`, `[b_R]`, `[a_NIR1]`, `[b_NIR1]` with your coefficients from the regression step.

```
run("32-bit");
saveAs("Tiff", "/tmp/test.tif");
run("Split Channels");

selectWindow("C3-test.tif");
run("Close");

// Red channel → R reflectance
selectWindow("C1-test.tif");
run("Multiply...", "value=[b_R]");
run("Exp");
run("Multiply...", "value=[a_R]");
saveAs("Tiff", "/tmp/R.tif");

// Green channel → NIR1 reflectance
selectWindow("C2-test.tif");
run("Multiply...", "value=[b_NIR1]");
run("Exp");
run("Multiply...", "value=[a_NIR1]");
saveAs("Tiff", "/tmp/IR1.tif");

// NDVI = (NIR1 - R) / (NIR1 + R)
imageCalculator("Subtract create 32-bit", "IR1.tif", "R.tif");
saveAs("Tiff", "/tmp/N1.tif");
imageCalculator("Add create 32-bit", "IR1.tif", "R.tif");
saveAs("Tiff", "/tmp/D1.tif");

selectWindow("R.tif");
close();
selectWindow("IR1.tif");
close();

imageCalculator("Divide create 32-bit", "N1.tif", "D1.tif");
selectWindow("Result of N1.tif");
run("NDVI_colors");
saveAs("Tiff", "/tmp/NDVI.tif");

selectWindow("D1.tif");
close();
selectWindow("N1.tif");
close();
```

## Colour Scale

In both scripts, `run("NDVI_colors")` applies the standard vegetation index colour scale:

| NDVI/NDRE value | Colour | Interpretation |
|---|---|---|
| Close to −1 | Black | Water, deep shadow |
| −1 to 0 | Grey tones | Non-photosynthetic surfaces (soil, rock, trunks, sky) |
| 0 to ~0.3 | Blue | Low photosynthetic activity (lichens, algae, sparse vegetation) |
| ~0.3 to ~0.6 | Green-yellow | Moderate photosynthetic activity (grass, shrubs) |
| Close to 1 | Red | High photosynthetic activity (dense healthy vegetation) |
