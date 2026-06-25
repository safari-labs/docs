# ColorChecker Photography

## Reference Data Preparation

Before collecting calibration photos, download the X-Rite ColorChecker spectral reflectance data from Ritchie et al. (2008), which covers all 24 panels at wavelengths from 400–900 nm including the NIR range required for this calibration. This published data is the same for all Macbeth ColorChecker devices as they are factory calibrated.

This data forms the Y variable (known reflectance) in both the wavelength characterization and the regression models.

## Photography Procedure

Place the Macbeth ColorChecker (11" × 8.25") flat on the ground facing incident light to avoid shadows. Position the camera 1 metre from the checker. Perform [Custom White Balance](cwb.md) before beginning.

Collect a minimum of 23 photographs covering the following range of conditions:

| Parameter | Range |
|---|---|
| Time of day | 10am–6pm |
| F-stop | f/4–f/16 |
| Shutter speed | 1/500s–1/6s |
| Focal length | Full range of your lens |

This range ensures the regression models are valid across the full variety of conditions encountered in field use. Vary one parameter at a time where possible to ensure adequate coverage of the parameter space.

Check the histogram after every shot and reject any underexposed or overexposed frames — see [White Balance](cwb.md#histogram-checking).

## RAW Conversion

Convert all ARW files to 16-bit linear TIFF using DCRAW. This preserves the exact quantitative sensor data without any post-processing, gamma correction, or white balance adjustment applied by the camera:

```bash
dcraw -v -r 1 1 1 1 -M -o 0 -q 3 -W -T -4 -g 1 1 -t 0 *.ARW
```

The `-r 1 1 1 1` flag is critical — it disables automatic channel weighting. The `-4` flag outputs 16-bit linear data. Do not use any other conversion settings as they will alter the linear relationship between sensor input and output that the regression models depend on.

## Histogram Equalization

Equalize all TIFF files to expand the brightness range to maximum amplitude, eliminating residual exposure differences between photographs:

```bash
for f in $(ls *.tif); do convert $f -auto-level $f; done
```

On Windows PowerShell:

```powershell
Get-ChildItem *.tif | ForEach-Object { magick $_.Name -auto-level $_.Name }
```

## ImageJ Measurement

Open each equalized TIFF in ImageJ and measure the mean brightness of each of the 24 ColorChecker panels in the R, G, and B channels:

1. Open the TIFF file in ImageJ
2. Go to Image → Color → Split Channels to separate R, G, B
3. For each channel, use the rectangular selection tool to select each panel
4. Record the mean brightness value from Analyze → Measure

Record results in a CSV with the following structure:

```
photo_id, time, fstop, speed, focal_length, panel_id, R_brightness, G_brightness, B_brightness
```

Target approximately 552 data points in total (23 photographs × 24 panels). This dataset feeds directly into both the wavelength characterization and the regression models.
