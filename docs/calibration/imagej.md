# ImageJ Scripts Reference

This page is a quick reference for both scripts with placeholder coefficient locations clearly marked. For the full decision logic on which script to use, see [Index Selection](index-selection.md).

## Your Calibration Coefficients

Record your coefficients here after completing the [Regression Models](regression.md) step:

| Model | a | b |
|---|---|---|
| Red (R) | | |
| NIR1 / Red-edge (G) | | |
| NIR2 / NIR (B) | | |

## Applying the Scripts

1. Open your equalized TIFF field photograph in ImageJ
2. Go to Plugins → Macros → Run
3. Select the appropriate script file
4. The output TIFF will be saved to `/tmp/` — move it to your working directory after running

## Batch Processing

To process multiple photographs, wrap either script in a batch loop using ImageJ's built-in batch processing:

1. Go to Process → Batch → Macro
2. Set input folder to your equalized TIFFs
3. Set output folder for your results
4. Paste the script content into the macro window
5. Click Process

This applies the script to every TIFF in the input folder automatically.

## Notes

- Scripts output 32-bit TIFF files — preserve this bit depth throughout analysis
- The `NDVI_colors` lookup table must be installed in ImageJ before running — it is included in the standard ImageJ distribution
- Coefficient values are camera-specific and must be recalculated if a different camera body or a different conversion is used
