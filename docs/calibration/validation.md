# Validation

## Purpose

Hierarchical Partitioning (HP) analysis tests whether any of the experimental factors — time of day, focal length, f-stop, and shutter speed — significantly explain the residuals of the regression models. If a factor is significant it means the calibration is not fully accounting for variation introduced by that shooting condition, and the regression coefficients will not be reliable across the full range of field conditions.

HP is used rather than standard ANOVA because the residuals are unlikely to meet the normality and variance homogeneity requirements of parametric analysis. HP uses a randomization test and shows the percentage of independent effect of each factor on the residuals.

## R Code

```r
library(hier.part)

# Prepare factor variables from your calibration data
factors <- data.frame(
  time         = your_data$time,
  focal_length = your_data$focal_length,
  fstop        = your_data$fstop,
  speed        = your_data$speed
)

# Validate each model
cat("=== Red channel residuals ===\n")
hier.part(residuals(model_R), factors)

cat("\n=== NIR1 channel residuals ===\n")
hier.part(residuals(model_NIR1), factors)

cat("\n=== NIR2 channel residuals ===\n")
hier.part(residuals(model_NIR2), factors)
```

## Interpreting the Output

For each model, HP reports the percentage of variance in the residuals attributable to each factor, along with a significance test. The target outcome is that **no factor is significant** for any model.

| Outcome | Meaning | Action |
|---|---|---|
| No factors significant | Calibration is robust across all tested conditions | Proceed to index selection |
| Time significant | Spectral composition of light varying with time of day not fully corrected by CWB | Tighten CWB procedure and reshoot |
| F-stop significant | Exposure variation not fully corrected | Check histogram equalization step |
| Shutter speed significant | As above | Check histogram equalization step |
| Focal length significant | Vignetting not fully corrected | Check CWB overexposure reference frame |

## Reshoot Criteria

If any factor is significant, identify the sessions contributing most to that factor's effect and reshoot them with more careful CWB and histogram checking. A single poorly controlled session can drive significance across all models. Refit the models and rerun HP after reshooting.
