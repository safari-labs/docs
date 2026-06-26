"""deploy/infer.py — Self-contained Jetson Orin inference script.

All model and I/O code is inlined here so this file has NO dependency on
the src/ package.  Only standard library + torch + numpy + rasterio +
matplotlib (for plotting) are required.

Usage (file mode):
    python deploy/infer.py --input sentinel2.tif --bands 3 4 5 \\
        --weights deploy/weights/fire_risk_best.pt --plot

Usage (live RabbitMQ pipeline):
    python deploy/infer.py --pipeline \\
        --weights deploy/weights/fire_risk_best.pt \\
        --amqp-url amqp://user:pass@jetson.local:5672/%2f
"""

import argparse
import datetime
import json
import math
import os
import sys
import threading
import time
import warnings
from pathlib import Path

for _cuda_dir in (
    "/usr/local/cuda/lib64",
    "/usr/local/cuda-12.2/lib64",
    "/usr/local/cuda-12.2/targets/aarch64-linux/lib",
    "/usr/local/cuda/targets/aarch64-linux/lib",
):
    if os.path.isdir(_cuda_dir) and _cuda_dir not in sys.path:
        sys.path.insert(0, _cuda_dir)

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors


# ===========================================================================
# Sensor profiles
# ===========================================================================

SENSOR_PROFILES: dict[str, dict] = {
    "full": {
        "description": "All 3 indices enabled (Red, RedEdge, NIR required)",
        "valid_indices": ["NDVI", "NDRE", "RRI2"],
        "mask": [1, 1, 1],
    },
    "a7sii": {
        "description": "Sony A7S II + 665nm PixelLife filter (Red=band1, NIR=band2)",
        "valid_indices": ["NDVI", "NDRE", "RRI2"],
        "mask": [1, 1, 1],
    },
    "sentinel2": {
        "description": "Sentinel-2 MSI — Red, RedEdge, NIR used",
        "valid_indices": ["NDVI", "NDRE", "RRI2"],
        "mask": [1, 1, 1],
    },
    "micasense": {
        "description": "MicaSense RedEdge — Red, RedEdge, NIR available",
        "valid_indices": ["NDVI", "NDRE", "RRI2"],
        "mask": [1, 1, 1],
    },
}

INDEX_NAMES = ["NDVI", "NDRE", "RRI2"]


# ===========================================================================
# 1. Differentiable Indices Layer
# ===========================================================================

class IndicesLayer(nn.Module):
    EPS = 1e-6

    def __init__(self, red_idx, nir_idx,
                 rededge_idx=None, sensor_mask=None,
                 use_raw_bands: bool = False):
        super().__init__()
        self.red_idx      = red_idx
        self.nir_idx      = nir_idx
        self.rededge_idx  = rededge_idx
        self.use_raw_bands = use_raw_bands
        self.n_out = 6 if use_raw_bands else 3
        mask = sensor_mask if sensor_mask is not None else [1.0, 1.0, 1.0]
        self.register_buffer(
            "sensor_mask",
            torch.tensor(mask, dtype=torch.float32).view(1, -1, 1, 1)
        )

    def forward(self, x):
        red = x[:, self.red_idx:self.red_idx+1]
        nir = x[:, self.nir_idx:self.nir_idx+1]

        nir_red_sum = nir + red + self.EPS
        ndvi = (nir - red) / nir_red_sum

        if self.rededge_idx is not None:
            rededge = x[:, self.rededge_idx:self.rededge_idx+1]
            ndre = (nir - rededge) / (nir + rededge + self.EPS)
            rri2 = torch.clamp(rededge / (red + self.EPS), 0.0, 5.0) / 5.0
        else:
            rededge = torch.zeros_like(ndvi)
            ndre    = torch.zeros_like(ndvi)
            rri2    = torch.zeros_like(ndvi)

        indices = torch.cat([ndvi, ndre, rri2], dim=1) * self.sensor_mask

        if self.use_raw_bands:
            raw = torch.cat([red, nir, rededge], dim=1)
            return torch.cat([indices, raw], dim=1)

        return indices


# ===========================================================================
# 2. Fire Risk CNN
# ===========================================================================

class _ConvBNReLU(nn.Sequential):
    def __init__(self, in_ch, out_ch, kernel=3, padding=1):
        super().__init__(
            nn.Conv2d(in_ch, out_ch, kernel, padding=padding,
                      padding_mode="zeros", bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )


class FireRiskCNN(nn.Module):
    def __init__(self, in_channels=3, base_ch=32, dropout=0.3):
        super().__init__()
        self.in_channels = in_channels

        self.enc1 = nn.Sequential(
            _ConvBNReLU(in_channels, base_ch),
            _ConvBNReLU(base_ch, base_ch),
        )
        self.enc2 = nn.Sequential(
            nn.MaxPool2d(2),
            _ConvBNReLU(base_ch, base_ch * 2),
            _ConvBNReLU(base_ch * 2, base_ch * 2),
        )
        self.enc3 = nn.Sequential(
            nn.MaxPool2d(2),
            _ConvBNReLU(base_ch * 2, base_ch * 4),
            _ConvBNReLU(base_ch * 4, base_ch * 4),
        )

        self.bottleneck = nn.Sequential(
            nn.MaxPool2d(2),
            _ConvBNReLU(base_ch * 4, base_ch * 4, padding=2),
            nn.Conv2d(base_ch * 4, base_ch * 4, 3, padding=4, dilation=4, bias=False),
            nn.BatchNorm2d(base_ch * 4),
            nn.ReLU(inplace=True),
            nn.Dropout2d(dropout),
        )

        self.up3  = nn.ConvTranspose2d(base_ch * 4, base_ch * 4, 2, stride=2)
        self.dec3 = nn.Sequential(
            _ConvBNReLU(base_ch * 8, base_ch * 4),
            _ConvBNReLU(base_ch * 4, base_ch * 4),
            nn.Dropout2d(dropout),
        )

        self.up2  = nn.ConvTranspose2d(base_ch * 4, base_ch * 2, 2, stride=2)
        self.dec2 = nn.Sequential(
            _ConvBNReLU(base_ch * 4, base_ch * 2),
            _ConvBNReLU(base_ch * 2, base_ch * 2),
            nn.Dropout2d(dropout),
        )

        self.up1  = nn.ConvTranspose2d(base_ch * 2, base_ch, 2, stride=2)
        self.dec1 = nn.Sequential(
            _ConvBNReLU(base_ch * 2, base_ch),
            _ConvBNReLU(base_ch, base_ch),
            nn.Dropout2d(dropout * 0.5),
        )

        self.head = nn.Sequential(
            nn.Conv2d(base_ch, 16, 1),
            nn.ReLU(inplace=True),
            nn.Conv2d(16, 1, 1),
            nn.Sigmoid(),
        )

        self._init_weights()

    def _init_weights(self) -> None:
        for m in self.modules():
            if isinstance(m, (nn.Conv2d, nn.ConvTranspose2d)):
                nn.init.kaiming_normal_(m.weight, mode="fan_out",
                                        nonlinearity="relu")
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)

        self._seed_enc1_physics()

    def _seed_enc1_physics(self) -> None:
        kaiming_std = (2.0 / (self.in_channels * 3 * 3)) ** 0.5

        sobel_x = torch.tensor(
            [[-1., 0., 1.], [-2., 0., 2.], [-1., 0., 1.]], dtype=torch.float32
        )
        sobel_y = sobel_x.T

        center_surround = torch.tensor(
            [[-1., -1., -1.],
             [-1.,  8., -1.],
             [-1., -1., -1.]], dtype=torch.float32
        )
        center_surround = -center_surround

        def _scaled(k: torch.Tensor) -> torch.Tensor:
            return k / k.norm() * kaiming_std

        cs_s      = _scaled(center_surround)
        sobel_x_s = _scaled(sobel_x)
        sobel_y_s = _scaled(sobel_y)

        seeds = [
            (0, 0, cs_s),
            (1, 1, cs_s),
            (2, 0, sobel_x_s),
            (3, 0, sobel_y_s),
            (4, 1, sobel_x_s),
            (5, 1, sobel_y_s),
            (6, 2, sobel_x_s),
            (7, 2, sobel_y_s),
        ]

        w = self.enc1[0][0].weight
        with torch.no_grad():
            for out_ch, in_ch, kernel in seeds:
                w[out_ch].zero_()
                w[out_ch, in_ch] = kernel

    @staticmethod
    def _pad_to_match(decoder: torch.Tensor,
                      encoder: torch.Tensor) -> torch.Tensor:
        diff_h = encoder.shape[2] - decoder.shape[2]
        diff_w = encoder.shape[3] - decoder.shape[3]
        if diff_h != 0 or diff_w != 0:
            decoder = F.pad(decoder, [0, diff_w, 0, diff_h])
        return decoder

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(e1)
        e3 = self.enc3(e2)

        b = self.bottleneck(e3)

        d3 = self._pad_to_match(self.up3(b), e3)
        d3 = self.dec3(torch.cat([d3, e3], dim=1))

        d2 = self._pad_to_match(self.up2(d3), e2)
        d2 = self.dec2(torch.cat([d2, e2], dim=1))

        d1 = self._pad_to_match(self.up1(d2), e1)
        d1 = self.dec1(torch.cat([d1, e1], dim=1))

        return self.head(d1)


# ===========================================================================
# 2b. Plain encoder-decoder baseline (no skip connections)
# ===========================================================================

class PlainEncDecCNN(nn.Module):
    def __init__(self, in_channels=3, base_ch=32, dropout=0.4):
        super().__init__()

        self.enc1 = nn.Sequential(
            _ConvBNReLU(in_channels, base_ch),
            _ConvBNReLU(base_ch, base_ch),
        )
        self.enc2 = nn.Sequential(
            nn.MaxPool2d(2),
            _ConvBNReLU(base_ch, base_ch * 2),
            _ConvBNReLU(base_ch * 2, base_ch * 2),
        )
        self.enc3 = nn.Sequential(
            nn.MaxPool2d(2),
            _ConvBNReLU(base_ch * 2, base_ch * 4),
            _ConvBNReLU(base_ch * 4, base_ch * 4),
        )
        self.bottleneck = nn.Sequential(
            _ConvBNReLU(base_ch * 4, base_ch * 4, padding=2),
            nn.Conv2d(base_ch * 4, base_ch * 4, 3, padding=4, dilation=4,
                      bias=False),
            nn.BatchNorm2d(base_ch * 4),
            nn.ReLU(inplace=True),
            nn.Dropout2d(dropout),
        )
        self.up2  = nn.ConvTranspose2d(base_ch * 4, base_ch * 2, 2, stride=2)
        self.dec2 = nn.Sequential(
            _ConvBNReLU(base_ch * 2, base_ch * 2),
            _ConvBNReLU(base_ch * 2, base_ch * 2),
            nn.Dropout2d(dropout),
        )
        self.up1  = nn.ConvTranspose2d(base_ch * 2, base_ch, 2, stride=2)
        self.dec1 = nn.Sequential(
            _ConvBNReLU(base_ch, base_ch),
            _ConvBNReLU(base_ch, base_ch),
            nn.Dropout2d(dropout * 0.5),
        )
        self.head = nn.Sequential(
            nn.Conv2d(base_ch, 16, 1),
            nn.ReLU(inplace=True),
            nn.Conv2d(16, 1, 1),
            nn.Sigmoid(),
        )
        for m in self.modules():
            if isinstance(m, (nn.Conv2d, nn.ConvTranspose2d)):
                nn.init.kaiming_normal_(m.weight, mode="fan_out",
                                        nonlinearity="relu")
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, x):
        e2 = self.enc2(self.enc1(x))
        e3 = self.enc3(e2)
        b  = self.bottleneck(e3)
        d2 = self.dec2(self.up2(b))
        d1 = self.dec1(self.up1(d2))
        return self.head(d1)


# ===========================================================================
# 3. End-to-end wrapper
# ===========================================================================

class FireRiskModel(nn.Module):
    LOW_THRESHOLD    = 0.3
    MEDIUM_THRESHOLD = 0.6

    def __init__(self, red_idx=0, nir_idx=1,
                 rededge_idx=None, base_ch=32, sensor_profile="full",
                 dropout=0.4, model_variant="unet",
                 use_raw_bands: bool = False):
        super().__init__()
        profile = SENSOR_PROFILES.get(sensor_profile, SENSOR_PROFILES["full"])
        sensor_mask = [float(v) for v in profile["mask"]]
        valid = profile["valid_indices"]
        in_channels = 6 if use_raw_bands else 3
        print(f"  Sensor profile: '{sensor_profile}' — {profile['description']}")
        print(f"  Active indices: {valid}")
        print(f"  Input channels: {in_channels} "
              f"({'indices + raw bands' if use_raw_bands else 'indices only'})")

        self.sensor_profile = sensor_profile
        self.valid_indices  = valid
        self.model_variant  = model_variant

        self.indices_layer = IndicesLayer(
            red_idx=red_idx, nir_idx=nir_idx,
            rededge_idx=rededge_idx,
            sensor_mask=sensor_mask,
            use_raw_bands=use_raw_bands,
        )
        if model_variant == "plain_encdec":
            self.cnn = PlainEncDecCNN(in_channels=in_channels, base_ch=base_ch,
                                      dropout=dropout)
        else:
            self.cnn = FireRiskCNN(in_channels=in_channels, base_ch=base_ch,
                                   dropout=dropout)

    def forward(self, x):
        indices = self.indices_layer(x)
        return self.cnn(indices)

    def predict(self, x, pad: int = 32):
        self.eval()
        with torch.no_grad():
            x_pad = F.pad(x, (pad, pad, pad, pad), mode="reflect")
            out   = self.forward(x_pad)
            return out[:, :, pad:-pad, pad:-pad]

    def get_indices(self, x):
        self.eval()
        with torch.no_grad():
            return self.indices_layer(x)

    def save(self, path):
        torch.save(self.state_dict(), path)
        print(f"Weights saved -> {path}")

    def load(self, path, device="cpu"):
        self.load_state_dict(torch.load(path, map_location=device))
        print(f"Weights loaded <- {path}")

    def export_onnx(self, path, n_bands, hw=256):
        self.eval()
        dummy = torch.zeros(1, n_bands, hw, hw)
        torch.onnx.export(
            self, dummy, path,
            input_names=["bands"], output_names=["risk_map"],
            opset_version=17,
            dynamic_axes={"bands": {0: "batch", 2: "H", 3: "W"},
                          "risk_map": {0: "batch", 2: "H", 3: "W"}},
        )
        print(f"ONNX exported -> {path}")


# ===========================================================================
# I/O helpers
# ===========================================================================

def load_tif_as_tensor(tif_path, band_indices, device="cpu"):
    try:
        import rasterio
    except ImportError:
        raise ImportError("pip install rasterio")

    bands = []
    with rasterio.open(tif_path) as src:
        meta = src.meta.copy()
        for idx in band_indices:
            band = src.read(idx).astype(np.float32)
            nodata = src.nodata
            if nodata is not None:
                band[band == nodata] = 0.0
            p2, p98 = np.percentile(band[band > 0], [2, 98]) if band.any() else (0, 1)
            band = np.clip((band - p2) / (p98 - p2 + 1e-6), 0.0, 1.0)
            bands.append(band)

    arr    = np.stack(bands, axis=0)
    tensor = torch.from_numpy(arr).float().unsqueeze(0).to(device)
    return tensor, meta, (arr.shape[1], arr.shape[2])


def load_tif_from_bytes(tiff_bytes: bytes, band_indices: list[int],
                        device: str = "cpu"):
    import io
    import rasterio

    bands = []
    with rasterio.open(io.BytesIO(tiff_bytes)) as src:
        meta = src.meta.copy()
        for idx in band_indices:
            band = src.read(idx).astype(np.float32)
            nodata = src.nodata
            if nodata is not None:
                band[band == nodata] = 0.0
            p2, p98 = np.percentile(band[band > 0], [2, 98]) if band.any() else (0, 1)
            band = np.clip((band - p2) / (p98 - p2 + 1e-6), 0.0, 1.0)
            bands.append(band)

    arr    = np.stack(bands, axis=0)
    tensor = torch.from_numpy(arr).float().unsqueeze(0).to(device)
    return tensor, meta, (arr.shape[1], arr.shape[2])


def save_risk_tif(risk_map, meta, output_path):
    try:
        import rasterio
    except ImportError:
        raise ImportError("pip install rasterio")

    meta.update({"count": 1, "dtype": "float32", "nodata": -1.0})
    with rasterio.open(output_path, "w", **meta) as dst:
        dst.write(risk_map, 1)
    print(f"Risk map saved -> {output_path}")


def plot_results(indices_tensor, risk_tensor, filename, nir_band=None,
                 save_path=None, valid_indices=None, buf=None, rgb_np=None):
    from matplotlib.gridspec import GridSpec

    indices = indices_tensor[0].cpu().numpy()
    risk    = risk_tensor[0, 0].cpu().numpy()

    fig = plt.figure(figsize=(20, 14))
    fig.suptitle(f"Fire Risk Analysis — {filename}", fontsize=15, fontweight="bold", y=0.98)

    gs_top = GridSpec(1, 4, figure=fig, top=0.90, bottom=0.63, wspace=0.05)
    n_mid  = 2 if rgb_np is not None else 1
    gs_mid = GridSpec(1, n_mid, figure=fig, top=0.58, bottom=0.30, wspace=0.05)
    gs_bot = GridSpec(1, 1, figure=fig, top=0.25, bottom=0.02)

    index_cmaps = [
        ["#8B4513","#FFFF00","#006400"],
        ["#5C3317","#FFF176","#1B5E20"],
        ["#8B2500","#FF6B35","#FFD700","#ADFF2F","#004000"],
    ]
    vmins = [-1, -1, 0]
    vmaxs = [ 1,  1, 1]

    ax_nir = fig.add_subplot(gs_top[0, 0])
    if nir_band is not None:
        ax_nir.imshow(nir_band, cmap="gray", vmin=0, vmax=1)
        ax_nir.set_title("NIR (raw)", fontsize=9, fontweight="bold")
    else:
        ax_nir.set_title("NIR (not provided)", fontsize=9, color="#aaaaaa")
    ax_nir.axis("off")

    for i, (name, cmap_colors, vmin, vmax) in enumerate(
        zip(INDEX_NAMES, index_cmaps, vmins, vmaxs)
    ):
        ax = fig.add_subplot(gs_top[0, i + 1])
        cmap = mcolors.LinearSegmentedColormap.from_list(name, cmap_colors)
        ax.imshow(indices[i], cmap=cmap, vmin=vmin, vmax=vmax)
        is_valid = valid_indices is None or name in valid_indices
        colour   = "black" if is_valid else "#aaaaaa"
        suffix   = "" if is_valid else " (N/A)"
        ax.set_title(name + suffix, fontsize=9, fontweight="bold", color=colour)
        ax.axis("off")
        if not is_valid:
            ax.text(0.5, 0.5, "Not valid\nfor this sensor",
                    transform=ax.transAxes, ha="center", va="center",
                    fontsize=8, color="#888888",
                    bbox=dict(boxstyle="round", fc="white", alpha=0.7))

    if rgb_np is not None:
        ax_rgb = fig.add_subplot(gs_mid[0, 0])
        ax_rgb.imshow(np.clip(rgb_np, 0, 1))
        ax_rgb.set_title("RGB (True Color)", fontsize=11)
        ax_rgb.axis("off")

    risk_cmap = mcolors.LinearSegmentedColormap.from_list(
        "fire_risk", ["#2ecc71", "#f39c12", "#e74c3c"]
    )
    risk_col  = 1 if rgb_np is not None else 0
    ax_risk   = fig.add_subplot(gs_mid[0, risk_col])
    im = ax_risk.imshow(risk, cmap=risk_cmap, vmin=0, vmax=1)

    if nir_band is not None:
        from scipy.ndimage import binary_closing
        water_mask = nir_band < 0.08
        water_mask = binary_closing(water_mask, iterations=2)
        if water_mask.any():
            ax_risk.contour(
                water_mask.astype(np.float32),
                levels   = [0.5],
                colors   = ["#1565c0"],
                linewidths = 0.8,
                alpha    = 0.9,
            )
            from matplotlib.lines import Line2D
            ax_risk.legend(
                handles = [Line2D([0], [0], color="#1565c0", linewidth=1.2,
                                  label="Water boundary")],
                loc       = "lower right",
                fontsize  = 8,
                framealpha= 0.6,
            )

    ax_risk.set_title("Fire Risk Score (0 = safe  →  1 = high risk)", fontsize=11)
    ax_risk.axis("off")
    plt.colorbar(im, ax=ax_risk, fraction=0.02, pad=0.01, label="Risk Score")

    ax_hist = fig.add_subplot(gs_bot[0, 0])
    ax_hist.hist(risk.flatten(), bins=100, color="#e74c3c", edgecolor="none", alpha=0.8)
    ax_hist.axvline(0.3, color="orange", linestyle="--", label="Medium threshold (0.3)")
    ax_hist.axvline(0.6, color="red",    linestyle="--", label="High threshold (0.6)")
    ax_hist.set_title("Risk Score Distribution")
    ax_hist.set_xlabel("Risk Score")
    ax_hist.set_ylabel("Pixel Count")
    ax_hist.legend(fontsize=9)

    total  = risk.size
    low    = np.sum(risk < 0.3)
    medium = np.sum((risk >= 0.3) & (risk < 0.6))
    high   = np.sum(risk >= 0.6)
    print(f"\n  Risk Zone Summary:")
    print(f"  Low    (< 0.3):   {low:>8,} px  ({low/total*100:5.1f}%)")
    print(f"  Medium (0.3-0.6): {medium:>8,} px  ({medium/total*100:5.1f}%)")
    print(f"  High   (> 0.6):   {high:>8,} px  ({high/total*100:5.1f}%)\n")

    if buf is not None:
        plt.savefig(buf, dpi=150, bbox_inches="tight", format="png")
    elif save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Plot saved -> {save_path}")
    else:
        plt.show()
    plt.close(fig)


def mask_clouds_from_bands(
    red: np.ndarray,
    nir: np.ndarray,
    brightness_threshold: float = 0.8,
    ndvi_threshold:       float = 0.05,
) -> np.ndarray:
    from scipy.ndimage import binary_dilation

    ndvi       = (nir - red) / (nir + red + 1e-6)
    brightness = (red + nir) / 2.0

    is_cloud = (brightness > brightness_threshold) & (ndvi < ndvi_threshold)
    is_cloud = binary_dilation(is_cloud, iterations=5)

    cloud_mask = (~is_cloud).astype(np.float32)
    cloudy_pct = (cloud_mask < 0.5).mean() * 100
    print(f"  Cloud coverage:      {cloudy_pct:.1f}% of image masked")
    return cloud_mask


def mask_non_vegetation(
    red:            np.ndarray,
    nir:            np.ndarray,
    ndvi_threshold: float = 0.2,
    min_nir:        float = 0.1,
) -> np.ndarray:
    ndvi          = (nir - red) / (nir + red + 1e-6)
    is_vegetation = (ndvi > ndvi_threshold) & (nir > min_nir)
    veg_mask      = is_vegetation.astype(np.float32)

    veg_pct = veg_mask.mean() * 100
    print(f"  Vegetation coverage: {veg_pct:.1f}%  "
          f"({100 - veg_pct:.1f}% masked as non-veg)")
    return veg_mask


def apply_masks(
    risk_map:           np.ndarray,
    red:                np.ndarray,
    nir:                np.ndarray,
    ndvi_veg_threshold: float = 0.2,
    cloud_brightness:   float = 0.8,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    print("\n  Applying masks...")
    cloud_mask  = mask_clouds_from_bands(red, nir,
                      brightness_threshold=cloud_brightness)
    veg_mask    = mask_non_vegetation(red, nir,
                      ndvi_threshold=ndvi_veg_threshold)
    combined    = cloud_mask * veg_mask
    masked_risk = risk_map * combined

    total_masked = (combined < 0.5).mean() * 100
    print(f"  Total masked:        {total_masked:.1f}% of image")
    return masked_risk, veg_mask, cloud_mask


def report_fire_hotspots(
    risk_np:      np.ndarray,
    meta:         dict,
    top_n:        int        = 10,
    threshold:    float      = 0.6,
    min_area_px:  int        = 9,
    geojson_path: str | None = None,
) -> list[dict]:
    """Detect contiguous fire-risk regions and report their geographic coordinates.

    Regions are ranked by area.  Centroids are reprojected to WGS-84 (lon/lat)
    when the GeoTIFF carries a CRS; otherwise pixel row/col are reported.

    Parameters
    ----------
    risk_np      : (H, W) float32 risk map in [0, 1]
    meta         : rasterio dataset metadata (needs 'transform' and 'crs')
    top_n        : number of regions to report
    threshold    : minimum risk score to classify as high-risk
    min_area_px  : discard regions smaller than this (noise filter)
    geojson_path : optional path to write a GeoJSON FeatureCollection (Points)
    """
    try:
        from scipy.ndimage import label as ndi_label
    except ImportError:
        print("  [hotspots] scipy not available — skipping hotspot report.")
        return []

    high_risk = risk_np >= threshold
    if not high_risk.any():
        print(f"\n  No high-risk pixels found (threshold ≥ {threshold:.2f}).")
        return []

    labeled, n_raw = ndi_label(high_risk)

    transform = meta.get("transform")
    crs       = meta.get("crs")
    has_geo   = transform is not None and crs is not None
    pixel_area_km2 = abs(transform.a * transform.e) / 1e6 if has_geo else None

    regions = []
    for rid in range(1, n_raw + 1):
        mask = labeled == rid
        n_px = int(mask.sum())
        if n_px < min_area_px:
            continue
        rows, cols = np.where(mask)
        regions.append({
            "_rid":         rid,
            "area_px":      n_px,
            "area_km2":     n_px * pixel_area_km2 if pixel_area_km2 else None,
            "mean_risk":    float(risk_np[mask].mean()),
            "centroid_row": float(rows.mean()),
            "centroid_col": float(cols.mean()),
        })

    if not regions:
        print(f"\n  No regions ≥ {min_area_px} px above threshold {threshold:.2f}.")
        return []

    regions.sort(key=lambda r: r["area_px"], reverse=True)
    top = regions[:top_n]

    if has_geo:
        import rasterio.transform as rt
        import rasterio.warp
        rows_c = [r["centroid_row"] for r in top]
        cols_c = [r["centroid_col"] for r in top]
        xs, ys = rt.xy(transform, rows_c, cols_c)
        try:
            lons, lats = rasterio.warp.transform(crs, "EPSG:4326", xs, ys)
            for r, lon, lat in zip(top, lons, lats):
                r["lon"] = round(float(lon), 6)
                r["lat"] = round(float(lat), 6)
        except Exception as exc:
            print(f"  [hotspots] CRS reprojection failed ({exc}) — reporting projected coords.")
            for r, x, y in zip(top, xs, ys):
                r["lon"] = round(float(x), 2)
                r["lat"] = round(float(y), 2)

    n_total_px     = int(high_risk.sum())
    total_area_km2 = n_total_px * pixel_area_km2 if pixel_area_km2 else None

    print(f"\n{'═' * 72}")
    print(f"  Fire Hotspot Report  "
          f"(threshold ≥ {threshold:.2f}  |  {len(regions)} regions  |  showing top {len(top)})")
    if total_area_km2 is not None:
        print(f"  Total high-risk area : {total_area_km2:.3f} km²")
    print(f"{'─' * 72}")
    if has_geo and "lat" in top[0]:
        print(f"  {'#':>3}  {'Latitude':>11}  {'Longitude':>12}  "
              f"{'Area (km²)':>10}  {'Confidence':>10}")
        print(f"  {'─'*3}  {'─'*11}  {'─'*12}  {'─'*10}  {'─'*10}")
        for i, r in enumerate(top, 1):
            print(f"  {i:>3}  {r['lat']:>10.5f}°  {r['lon']:>11.5f}°  "
                  f"{r['area_km2']:>10.4f}  {r['mean_risk']:>10.3f}")
    else:
        print(f"  {'#':>3}  {'Row':>8}  {'Col':>8}  {'Area (px)':>10}  {'Confidence':>10}")
        print(f"  {'─'*3}  {'─'*8}  {'─'*8}  {'─'*10}  {'─'*10}")
        for i, r in enumerate(top, 1):
            print(f"  {i:>3}  {r['centroid_row']:>8.1f}  {r['centroid_col']:>8.1f}  "
                  f"{r['area_px']:>10,}  {r['mean_risk']:>10.3f}")
    print(f"{'═' * 72}")

    if geojson_path and has_geo:
        import rasterio.features
        import rasterio.warp
        features = []
        need_reproject = str(crs).upper() not in ("EPSG:4326", "WGS 84", "WGS84")
        for i, r in enumerate(top, 1):
            region_mask = (labeled == r["_rid"]).astype(np.uint8)
            shapes = list(rasterio.features.shapes(
                region_mask, mask=region_mask, transform=transform,
            ))
            if not shapes:
                continue
            # shapes() may return multiple rings for one region; merge via the
            # largest polygon (first one is always the exterior in practice)
            geom = shapes[0][0]
            if need_reproject:
                try:
                    geom = rasterio.warp.transform_geom(crs, "EPSG:4326", geom)
                except Exception as exc:
                    print(f"  [hotspots] polygon reproject failed for region {i}: {exc}")
            props = {
                "rank":       i,
                "area_km2":   round(r["area_km2"], 6) if r["area_km2"] else None,
                "area_px":    r["area_px"],
                "confidence": round(r["mean_risk"], 4),
            }
            if "lat" in r:
                props["centroid_lat"] = r["lat"]
                props["centroid_lon"] = r["lon"]
            features.append({"type": "Feature", "geometry": geom, "properties": props})
        Path(geojson_path).write_text(
            json.dumps({"type": "FeatureCollection", "features": features},
                       indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  GeoJSON saved -> {geojson_path}  ({len(features)} polygon(s))")

    return top


def inspect_thresholds(tif_path: str, red_band: int = 1, nir_band: int = 2) -> None:
    import rasterio

    with rasterio.open(tif_path) as src:
        red_raw = src.read(red_band).astype(np.float32)
        nir_raw = src.read(nir_band).astype(np.float32)

    def norm(arr):
        valid = arr[arr > 0]
        p2, p98 = np.percentile(valid, [2, 98]) if valid.size else (0, 1)
        return np.clip((arr - p2) / (p98 - p2 + 1e-6), 0.0, 1.0)

    red    = norm(red_raw)
    nir    = norm(nir_raw)
    ndvi   = (nir - red) / (nir + red + 1e-6)
    bright = (red + nir) / 2.0

    print("\n── Band statistics ────────────────────────────────────────────")
    print(f"  Red    mean={red.mean():.3f}  std={red.std():.3f}  "
          f"p5={np.percentile(red,   5):.3f}  p95={np.percentile(red,   95):.3f}")
    print(f"  NIR    mean={nir.mean():.3f}  std={nir.std():.3f}  "
          f"p5={np.percentile(nir,   5):.3f}  p95={np.percentile(nir,   95):.3f}")
    print(f"  NDVI   mean={ndvi.mean():.3f}  std={ndvi.std():.3f}  "
          f"p5={np.percentile(ndvi,  5):.3f}  p95={np.percentile(ndvi,  95):.3f}")
    print(f"  Bright mean={bright.mean():.3f}  "
          f"p95={np.percentile(bright, 95):.3f}  max={bright.max():.3f}")
    print("\n── Suggested thresholds ───────────────────────────────────────")
    print(f"  --ndvi-threshold   {np.percentile(ndvi,   20):.2f}   "
          f"(20th-pct NDVI  — separates veg from bare/urban)")
    print(f"  --cloud-brightness {np.percentile(bright, 97):.2f}   "
          f"(97th-pct bright — flags cloud pixels)")
    print()


# ===========================================================================
# Model loading — CNN only (no foundation models for Jetson deployment)
# ===========================================================================

def load_model(
    red_idx:        int,
    nir_idx:        int,
    rededge_idx:    int | None,
    sensor_profile: str,
    device:         str,
    base_ch:        int        = 32,
    weights_path:   str | None = None,
    model_variant:  str        = "unet",
    use_raw_bands:  bool       = False,
) -> "FireRiskModel":
    """Construct and initialise a FireRiskModel (CNN only — no foundation models)."""
    model = FireRiskModel(
        red_idx        = red_idx,
        nir_idx        = nir_idx,
        rededge_idx    = rededge_idx,
        base_ch        = base_ch,
        sensor_profile = sensor_profile,
        model_variant  = model_variant,
        use_raw_bands  = use_raw_bands,
    ).to(device)

    if device == "cuda" and torch.cuda.get_device_capability()[0] >= 8:
        model = model.to(memory_format=torch.channels_last)

    if weights_path:
        print(f"  Init strategy: load weights  ({weights_path})")
        state = torch.load(weights_path, map_location=device)
        missing, unexpected = model.load_state_dict(state, strict=False)
        if missing:
            print(f"  [INFO] {len(missing)} new layer(s) randomly initialised: "
                  f"{', '.join(missing)}")
        if unexpected:
            print(f"  [INFO] {len(unexpected)} key(s) from checkpoint not used: "
                  f"{', '.join(unexpected)}")
        print(f"Weights loaded <- {weights_path}")
    else:
        print("  Init strategy: fresh Kaiming init  (no weights provided)")

    return model


# ===========================================================================
# RabbitMQ pipeline defaults
# ===========================================================================

PIPELINE_DEFAULTS = {
    "url":           "amqp://ffed:changeme@jetson.local:5672/%2f",
    "tiff_exchange": "tiff_queue",
    "out_exchange":  "model_data_queue",
}


def run_pipeline(band_1based: dict, model_kwargs: dict,
                 amqp_url: str       = PIPELINE_DEFAULTS["url"],
                 tiff_exchange: str  = PIPELINE_DEFAULTS["tiff_exchange"],
                 out_exchange: str   = PIPELINE_DEFAULTS["out_exchange"],
                 plot_save_dir: str | None = None,
                 apply_masking: bool = False,
                 ndvi_veg_threshold: float = 0.2,
                 cloud_brightness:   float = 0.8):
    try:
        import pika
    except ImportError:
        raise ImportError("pip install pika")
    import datetime as dt
    import io
    import json as _json
    import sys as _sys
    import uuid

    BAND_PRIORITY = ["red", "nir", "rededge"]
    ordered_bands = [b for b in BAND_PRIORITY if band_1based.get(b)]
    band_indices_1based = [band_1based[b] for b in ordered_bands]
    ch = {name: i for i, name in enumerate(ordered_bands)}

    device         = model_kwargs.get("device", "cpu")
    weights_path   = model_kwargs.get("weights_path")
    sensor_profile = model_kwargs.get("sensor_profile", "full")

    model = FireRiskModel(
        red_idx        = ch["red"],
        nir_idx        = ch["nir"],
        rededge_idx    = ch.get("rededge", None),
        sensor_profile = sensor_profile,
    ).to(device)

    if weights_path:
        model.load(weights_path, device)
    else:
        print("  WARNING: No weights provided — pipeline running with random weights.")

    if plot_save_dir:
        Path(plot_save_dir).mkdir(parents=True, exist_ok=True)

    params = pika.URLParameters(amqp_url)
    params.connection_attempts = 3
    params.retry_delay         = 2
    params.socket_timeout      = 10
    params.heartbeat           = 60

    print(f"  Connecting to RabbitMQ at {amqp_url} ...")
    try:
        connection = pika.BlockingConnection(params)
    except pika.exceptions.AMQPConnectionError as exc:
        cause = exc.args[0] if exc.args else exc
        print(f"\n  ERROR: Could not connect to RabbitMQ.")
        print(f"  Reason: {cause}")
        print(f"\n  Checklist:")
        print(f"    1. Is RabbitMQ running?  (check Services or 'rabbitmqctl status')")
        print(f"    2. Is the broker reachable at the host/port in --amqp-url?")
        print(f"    3. Are the credentials correct?  (user:password in the URL)")
        print(f"    4. Is the vhost correct?  (%2f = '/' — the default vhost)")
        raise SystemExit(1)
    channel = connection.channel()

    channel.exchange_declare(exchange=tiff_exchange, exchange_type="fanout", durable=True)
    channel.exchange_declare(exchange=out_exchange,  exchange_type="fanout", durable=True)

    session    = uuid.uuid4().hex[:8]
    queue_name = f"fire_risk.{session}.{tiff_exchange}"
    channel.queue_declare(queue=queue_name, durable=False, exclusive=False, auto_delete=True)
    channel.queue_bind(queue=queue_name, exchange=tiff_exchange, routing_key="")

    print(f"  Pipeline connected: {amqp_url}")
    print(f"  Consuming from exchange '{tiff_exchange}' via queue '{queue_name}'")
    print(f"  Publishing JSON     to   exchange '{out_exchange}'")
    print("  Press Ctrl+C to stop.\n")

    def on_tiff_message(ch_mq, method, properties, body):
        import io as _io

        timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
        msg_id    = getattr(properties, "message_id", None) or uuid.uuid4().hex[:8]
        filename  = f"pipeline_{msg_id}.tiff"

        msg_log_buf  = _io.StringIO()
        _real_stdout = _sys.stdout

        class _MsgTee:
            def write(self, data):
                _real_stdout.write(data)
                msg_log_buf.write(data)
            def flush(self):
                _real_stdout.flush()

        _sys.stdout = _MsgTee()

        try:
            print(f"[{timestamp}]  Received {len(body):,} bytes  (id={msg_id})")

            tensor, meta, (H, W) = load_tif_from_bytes(body, band_indices_1based, device)
            print(f"  Image: {W} x {H} px")

            indices_tensor = model.get_indices(tensor).cpu()
            risk_tensor    = model.predict(tensor).cpu()
            risk_np        = risk_tensor[0, 0].numpy()

            if apply_masking:
                red_np = tensor[0, ch["red"]].cpu().numpy()
                nir_np = tensor[0, ch["nir"]].cpu().numpy()
                risk_np, _, _ = apply_masks(
                    risk_np, red_np, nir_np,
                    ndvi_veg_threshold = ndvi_veg_threshold,
                    cloud_brightness   = cloud_brightness,
                )

            total  = risk_np.size
            low    = int(np.sum(risk_np < 0.3))
            medium = int(np.sum((risk_np >= 0.3) & (risk_np < 0.6)))
            high   = int(np.sum(risk_np >= 0.6))

            result = {
                "ts":         timestamp,
                "message_id": msg_id,
                "image_w":    W,
                "image_h":    H,
                "risk_min":   float(risk_np.min()),
                "risk_max":   float(risk_np.max()),
                "risk_mean":  float(risk_np.mean()),
                "low_pct":    round(low    / total * 100, 2),
                "medium_pct": round(medium / total * 100, 2),
                "high_pct":   round(high   / total * 100, 2),
                "masked":     apply_masking,
            }

            print(f"  Risk — min:{result['risk_min']:.3f}  "
                  f"max:{result['risk_max']:.3f}  mean:{result['risk_mean']:.3f}")
            print(f"  Zones — low:{result['low_pct']}%  "
                  f"medium:{result['medium_pct']}%  high:{result['high_pct']}%")

            hotspots = report_fire_hotspots(risk_np, meta, top_n=10, threshold=0.6)
            result["hotspots"] = [
                {k: v for k, v in r.items()
                 if k in ("lat", "lon", "area_km2", "area_px", "mean_risk")}
                for r in hotspots
            ]

            nir_np  = tensor[0, ch["nir"]].cpu().numpy()
            risk_t  = torch.from_numpy(risk_np).unsqueeze(0).unsqueeze(0)
            png_buf = _io.BytesIO()
            plot_results(indices_tensor, risk_t, filename,
                         nir_band      = nir_np,
                         valid_indices = model.valid_indices,
                         buf           = png_buf)
            png_bytes = png_buf.getvalue()

            _sys.stdout = _real_stdout
            log_text    = msg_log_buf.getvalue()
            log_lines   = log_text.splitlines()

            common_headers = {
                "image_w":   str(W),
                "image_h":   str(H),
                "risk_mean": str(round(result["risk_mean"], 4)),
                "high_pct":  str(result["high_pct"]),
                "message_id": msg_id,
            }

            channel.basic_publish(
                exchange    = out_exchange,
                routing_key = "",
                body        = png_bytes,
                properties  = pika.BasicProperties(
                    content_type  = "image/png",
                    delivery_mode = 2,
                    message_id    = msg_id,
                    headers       = common_headers,
                ),
            )
            print(f"  PNG published   -> '{out_exchange}'  ({len(png_bytes):,} bytes)")

            payload = {
                **result,
                "log_lines": log_lines,
            }
            payload_bytes = _json.dumps(payload, ensure_ascii=False).encode("utf-8")

            channel.basic_publish(
                exchange    = out_exchange,
                routing_key = "",
                body        = payload_bytes,
                properties  = pika.BasicProperties(
                    content_type  = "application/json",
                    delivery_mode = 2,
                    message_id    = msg_id,
                    headers       = {**common_headers, "log_lines": str(len(log_lines))},
                ),
            )
            print(f"  JSON published  -> '{out_exchange}'  "
                  f"({len(payload_bytes):,} bytes, {len(log_lines)} log lines)")

            if plot_save_dir:
                save_path = str(Path(plot_save_dir) / f"{msg_id}.png")
                Path(save_path).write_bytes(png_bytes)
                print(f"  PNG saved       -> {save_path}")

            ch_mq.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as exc:
            _sys.stdout = _real_stdout
            print(f"  ERROR processing message {msg_id}: {exc}")
            ch_mq.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        finally:
            _sys.stdout = _real_stdout

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=queue_name, on_message_callback=on_tiff_message,
                          auto_ack=False)

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("\nPipeline stopped.")
    finally:
        if channel.is_open:
            channel.close()
        if connection.is_open:
            connection.close()


def publish_log(log_path: str, amqp_url: str, log_exchange: str = "log_queue") -> None:
    try:
        import pika
    except ImportError:
        print("  WARNING: pika not installed — log not published to RabbitMQ.")
        return

    log_text  = Path(log_path).read_text(encoding="utf-8", errors="replace")
    log_lines = log_text.count("\n")
    msg_id    = Path(log_path).stem

    params = pika.URLParameters(amqp_url)
    params.connection_attempts = 2
    params.retry_delay         = 1
    params.socket_timeout      = 8

    try:
        connection = pika.BlockingConnection(params)
        channel    = connection.channel()
        channel.exchange_declare(exchange=log_exchange,
                                 exchange_type="fanout", durable=True)
        channel.basic_publish(
            exchange    = log_exchange,
            routing_key = "",
            body        = log_text.encode("utf-8"),
            properties  = pika.BasicProperties(
                content_type  = "text/plain",
                delivery_mode = 2,
                message_id    = msg_id,
                headers       = {
                    "log_file":  Path(log_path).name,
                    "log_lines": str(log_lines),
                },
            ),
        )
        print(f"  Log published   -> '{log_exchange}'  ({len(log_text):,} chars, {log_lines} lines)")
        channel.close()
        connection.close()
    except Exception as exc:
        print(f"  WARNING: Could not publish log to RabbitMQ: {exc}")


class _Tee:
    def __init__(self, file_handle):
        import sys
        self._file   = file_handle
        self._stdout = sys.stdout
        sys.stdout   = self

    def write(self, data):
        self._stdout.write(data)
        self._file.write(data)

    def flush(self):
        self._stdout.flush()
        self._file.flush()

    def close(self):
        import sys
        sys.stdout = self._stdout
        self._file.close()


# ===========================================================================
# Inference entry point
# ===========================================================================

def run(input_path, band_1based, weights_path=None, save_risk=None,
        show_plot=True, save_plot=None, export_onnx=None, device="cpu",
        sensor_profile="full",
        apply_masking=False, ndvi_veg_threshold=0.2, cloud_brightness=0.8,
        geojson_path=None, top_n=10, hotspot_threshold=0.6,
        rgb_indices=None):

    filename = Path(input_path).name
    print(f"\nFireRiskModel — {filename}")

    if not band_1based.get("red"):
        raise ValueError("--red band index is required")
    if not band_1based.get("nir"):
        raise ValueError("--nir band index is required")

    BAND_PRIORITY = ["red", "nir", "rededge"]
    ordered_bands = [b for b in BAND_PRIORITY if band_1based.get(b)]
    band_indices_1based = [band_1based[b] for b in ordered_bands]
    ch = {name: i for i, name in enumerate(ordered_bands)}

    tensor, meta, (H, W) = load_tif_as_tensor(input_path, band_indices_1based, device)
    print(f"  Image: {W} x {H} px  |  Bands loaded: {ordered_bands}")

    rgb_np = None
    if rgb_indices:
        rgb_t, _, _ = load_tif_as_tensor(input_path, rgb_indices, "cpu")
        rgb_np = rgb_t[0].permute(1, 2, 0).numpy()  # (H, W, 3)

    model = load_model(
        red_idx        = ch["red"],
        nir_idx        = ch["nir"],
        rededge_idx    = ch.get("rededge", None),
        sensor_profile = sensor_profile,
        device         = device,
        weights_path   = weights_path,
    )

    total_params = sum(p.numel() for p in model.parameters())
    print(f"  Model parameters: {total_params:,}")

    indices_tensor = model.get_indices(tensor).cpu()
    risk_tensor    = model.predict(tensor).cpu()

    print(f"  Risk range: [{risk_tensor.min():.3f}, {risk_tensor.max():.3f}]")

    if apply_masking:
        red_np = tensor[0, ch["red"]].cpu().numpy()
        nir_np = tensor[0, ch["nir"]].cpu().numpy()
        risk_np, veg_mask, cloud_mask = apply_masks(
            risk_tensor[0, 0].numpy(), red_np, nir_np,
            ndvi_veg_threshold = ndvi_veg_threshold,
            cloud_brightness   = cloud_brightness,
        )
        risk_tensor = torch.from_numpy(risk_np).unsqueeze(0).unsqueeze(0)

    report_fire_hotspots(
        risk_tensor[0, 0].numpy(), meta,
        top_n=top_n, threshold=hotspot_threshold, geojson_path=geojson_path,
    )

    if save_risk:
        save_risk_tif(risk_tensor[0, 0].numpy(), meta, save_risk)

    if show_plot or save_plot:
        nir_np = tensor[0, ch["nir"]].cpu().numpy()
        plot_results(indices_tensor, risk_tensor, filename,
                     nir_band      = nir_np,
                     save_path     = save_plot,
                     valid_indices = model.valid_indices,
                     rgb_np        = rgb_np)

    if export_onnx:
        model.export_onnx(export_onnx, n_bands=len(ordered_bands))

    return indices_tensor, risk_tensor


# ===========================================================================
# CLI
# ===========================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Fire risk detection from multispectral GeoTIFF (Jetson deployment).",
    )
    parser.add_argument("--input",       default=None)
    parser.add_argument(
        "--bands", nargs="+", type=int, default=None, metavar="IDX",
        help="1-based band indices for the input GeoTIFF: R N [RE].",
    )
    parser.add_argument(
        "--rgb-bands", nargs=3, type=int, default=None, metavar="IDX",
        help="1-based band indices for the RGB display panel: R G B (e.g. 1 2 3).",
    )
    parser.add_argument("--weights",     default=None)
    parser.add_argument("--save-risk",   default=None)
    parser.add_argument("--plot",        action="store_true")
    parser.add_argument("--plot-save",   default=None)
    parser.add_argument("--export-onnx", default=None)
    parser.add_argument("--device",      default="cpu")
    parser.add_argument("--sensor-profile", default="full",
                        choices=list(SENSOR_PROFILES.keys()))
    parser.add_argument("--mask",             action="store_true")
    parser.add_argument("--ndvi-threshold",   type=float, default=0.2)
    parser.add_argument("--cloud-brightness", type=float, default=0.8)
    parser.add_argument("--inspect-thresholds", action="store_true")
    parser.add_argument("--geojson",            default=None, metavar="FILE",
                        help="Save hotspot centroids as a GeoJSON FeatureCollection.")
    parser.add_argument("--top-n",              type=int,   default=10,
                        help="Number of top hotspot regions to report (default: 10).")
    parser.add_argument("--hotspot-threshold",  type=float, default=0.6,
                        help="Risk score threshold for hotspot detection (default: 0.6).")
    parser.add_argument("--log", default=None, metavar="FILE")
    parser.add_argument("--pipeline",    action="store_true")
    parser.add_argument("--amqp-url",    default=PIPELINE_DEFAULTS["url"])
    parser.add_argument("--tiff-exchange",  default=PIPELINE_DEFAULTS["tiff_exchange"])
    parser.add_argument("--out-exchange",   default=PIPELINE_DEFAULTS["out_exchange"])
    parser.add_argument("--plot-save-dir",  default=None)
    parser.add_argument("--log-exchange",   default=PIPELINE_DEFAULTS["out_exchange"])
    parser.add_argument(
        "--model",
        choices=["unet", "plain_encdec"],
        default="unet",
        help="Model architecture: 'unet' (default) or 'plain_encdec' (no skip connections).",
    )
    parser.add_argument(
        "--raw-bands", action="store_true",
        help="Concatenate normalised raw bands with spectral indices (6-channel input).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    _bands_r  = args.bands[0] if args.bands else None
    _bands_n  = args.bands[1] if args.bands and len(args.bands) > 1 else None
    _bands_re = args.bands[2] if args.bands and len(args.bands) > 2 else None

    _tee = None
    if args.log:
        _log_file = open(args.log, "w", encoding="utf-8", buffering=1)
        _tee = _Tee(_log_file)
        print(f"Logging output to: {args.log}")

    if args.inspect_thresholds:
        if not _bands_r or not _bands_n:
            print("--inspect-thresholds requires --bands R N [RE]")
        else:
            inspect_thresholds(args.input,
                               red_band=_bands_r, nir_band=_bands_n)
        import sys; sys.exit(0)

    if not args.pipeline and not args.input:
        print("ERROR: provide --input <file> for file mode, or --pipeline for RabbitMQ mode.")
        import sys; sys.exit(1)

    _default_red     = 0
    _default_nir     = 1
    _default_rededge = 2
    band_1based = {
        "red":     _bands_r  if _bands_r  is not None else _default_red,
        "nir":     _bands_n  if _bands_n  is not None else _default_nir,
        "rededge": _bands_re if _bands_re is not None else _default_rededge,
    }

    if args.pipeline:
        run_pipeline(
            band_1based         = band_1based,
            model_kwargs        = {
                "device":         args.device,
                "weights_path":   args.weights,
                "sensor_profile": args.sensor_profile,
            },
            amqp_url            = args.amqp_url,
            tiff_exchange       = args.tiff_exchange,
            out_exchange        = args.out_exchange,
            plot_save_dir       = args.plot_save_dir,
            apply_masking       = args.mask,
            ndvi_veg_threshold  = args.ndvi_threshold,
            cloud_brightness    = args.cloud_brightness,
        )
        if _tee:
            print(f"\nLog saved -> {args.log}")
            _tee.close()
        import sys; sys.exit(0)

    run(
        input_path          = args.input,
        band_1based         = band_1based,
        weights_path        = args.weights,
        save_risk           = args.save_risk,
        show_plot           = args.plot,
        save_plot           = args.plot_save,
        export_onnx         = args.export_onnx,
        device              = args.device,
        sensor_profile      = args.sensor_profile,
        apply_masking       = args.mask,
        ndvi_veg_threshold  = args.ndvi_threshold,
        cloud_brightness    = args.cloud_brightness,
        geojson_path        = args.geojson,
        top_n               = args.top_n,
        hotspot_threshold   = args.hotspot_threshold,
        rgb_indices         = args.rgb_bands,
    )

    if _tee:
        print(f"\nLog saved -> {args.log}")
        _tee.close()

    if args.log and getattr(args, "amqp_url", None):
        publish_log(
            log_path     = args.log,
            amqp_url     = args.amqp_url,
            log_exchange = args.log_exchange,
        )
