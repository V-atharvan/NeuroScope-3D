"""
NeuroScope 3D - Standalone Inference Pipeline CLI
Executes preprocessing, model forward pass, nesting enforcement, BraTS 2021 label conversion,
grid restoration, and NIfTI output writing.
Independent of web application.
"""
import argparse
import os
import sys
import time
import numpy as np
import nibabel as nib

from inference.preprocessing import preprocess_study, PreprocessingError
from inference.postprocessing import (
    enforce_nesting_and_convert_labels,
    restore_original_grid,
    validate_label_map,
    derive_region_masks,
    PostprocessingError,
)


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description="NeuroScope 3D Standalone Inference Pipeline. Research/teaching only."
    )
    parser.add_argument("--t1", required=True, help="Path to T1-weighted NIfTI file")
    parser.add_argument("--t1gd", required=True, help="Path to T1Gd (contrast) NIfTI file")
    parser.add_argument("--t2", required=True, help="Path to T2-weighted NIfTI file")
    parser.add_argument("--flair", required=True, help="Path to FLAIR NIfTI file")
    parser.add_argument("--output", required=True, help="Output path for predicted BraTS 2021 label map (.nii or .nii.gz)")
    parser.add_argument("--weights", default=os.getenv("MODEL_WEIGHTS_PATH", "models/brats_mri_segmentation/models/model.pt"),
                        help="Path to pretrained model weights (checkpoint .pt)")
    parser.add_argument("--device", default=os.getenv("MODEL_DEVICE", "cpu"), choices=["cuda", "cpu"],
                        help="Inference device (cuda or cpu)")
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="Probability threshold for subregions (default: 0.5)")
    return parser.parse_args(args)


def run_model_inference(
    preprocessed_tensor: np.ndarray,
    weights_path: str,
    device_name: str = "cpu"
) -> np.ndarray:
    """
    Executes SegResNet model forward pass via PyTorch / MONAI.
    Expects input shape (4, H, W, D).
    Returns raw 3-channel logits or probabilities with shape (3, H, W, D).
    """
    try:
        import torch
        from monai.networks.nets import SegResNet
        from monai.inferers import SlidingWindowInferer
    except ImportError as e:
        raise RuntimeError(
            f"Missing deep learning dependency for model execution: {e}. "
            "Please ensure torch and monai are installed."
        )

    if not os.path.exists(weights_path):
        raise FileNotFoundError(
            f"Pretrained model weights not found at '{weights_path}'. "
            "Download or specify the MONAI brats_mri_segmentation bundle weights via --weights."
        )

    device = torch.device(device_name if torch.cuda.is_available() and device_name == "cuda" else "cpu")

    # Instantiate SegResNet adhering strictly to bundle config
    model = SegResNet(
        spatial_dims=3,
        in_channels=4,
        out_channels=3,
        init_filters=16,
        blocks_down=[1, 2, 2, 4],
        blocks_up=[1, 1, 1],
        dropout_prob=0.2,
    ).to(device)

    # Load weights
    checkpoint = torch.load(weights_path, map_location=device)
    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        model.load_state_dict(checkpoint["state_dict"])
    elif isinstance(checkpoint, dict) and "model" in checkpoint:
        model.load_state_dict(checkpoint["model"])
    elif isinstance(checkpoint, dict):
        model.load_state_dict(checkpoint)
    else:
        model = checkpoint

    model.eval()

    # Configure sliding window inferer matching configs/inference.json
    inferer = SlidingWindowInferer(
        roi_size=[240, 240, 160],
        sw_batch_size=1,
        overlap=0.5,
        mode="gaussian",
    )

    input_tensor = torch.from_numpy(preprocessed_tensor).unsqueeze(0).to(device)  # shape (1, 4, H, W, D)

    with torch.no_grad():
        raw_output = inferer(input_tensor, model)  # shape (1, 3, H, W, D)

    output_np = raw_output.squeeze(0).cpu().numpy().astype(np.float32)  # shape (3, H, W, D)
    return output_np


def run_pipeline(
    t1: str,
    t1gd: str,
    t2: str,
    flair: str,
    output: str,
    weights: str = "models/brats_mri_segmentation/models/model.pt",
    device: str = "cpu",
    threshold: float = 0.5,
) -> str:
    """
    Main orchestrator for standalone inference.
    Executes full pipeline and writes BraTS 2021 NIfTI file on original grid.
    """
    start_time = time.time()
    sequence_paths = {"t1": t1, "t1gd": t1gd, "t2": t2, "flair": flair}

    print("[NeuroScope 3D] Starting standalone inference pipeline...")
    print(f"[NeuroScope 3D] Device requested: {device}")

    # 1. Preprocessing
    print("[NeuroScope 3D] Loading and validating sequences [T1Gd, T1, T2, FLAIR]...")
    tensor, meta = preprocess_study(sequence_paths)
    print(f"[NeuroScope 3D] Preprocessed tensor shape: {tensor.shape}")

    # 2. Forward Pass
    print(f"[NeuroScope 3D] Running SegResNet inference (weights: {weights})...")
    raw_channels = run_model_inference(tensor, weights_path=weights, device_name=device)
    print(f"[NeuroScope 3D] Raw model output shape: {raw_channels.shape} (Channels: 0=TC, 1=WT, 2=ET)")

    # 3. Postprocessing: Nesting & BraTS Label Conversion
    print(f"[NeuroScope 3D] Applying threshold {threshold}, enforcing ET ⊆ TC ⊆ WT, and mapping BraTS labels...")
    label_map = enforce_nesting_and_convert_labels(raw_channels, threshold=threshold, is_logits=True)

    # 4. Restore Original Grid
    original_shape = tuple(meta["original_shape"])
    print(f"[NeuroScope 3D] Restoring original spatial grid {original_shape} with nearest-neighbour interpolation...")
    restored_labels = restore_original_grid(label_map, target_shape=original_shape)

    # 5. Validation of Output
    validate_label_map(restored_labels, expected_shape=original_shape)
    unique_labels = sorted(np.unique(restored_labels).tolist())
    print(f"[NeuroScope 3D] Output label validation passed. Unique labels present: {unique_labels}")

    # 6. Region Breakdown Summary
    region_masks = derive_region_masks(restored_labels)
    voxel_spacing = meta["voxel_spacing_mm"]
    voxel_vol_ml = (voxel_spacing[0] * voxel_spacing[1] * voxel_spacing[2]) / 1000.0

    print("[NeuroScope 3D] Derived region summary:")
    for region_name, mask in region_masks.items():
        vcount = int(np.sum(mask))
        vml = vcount * voxel_vol_ml
        print(f"  - {region_name}: {vcount} voxels ({vml:.2f} mL)")

    # 7. Write NIfTI file to disk
    output_dir = os.path.dirname(os.path.abspath(output))
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    ref_affine = meta["ref_affine_np"]
    ref_header = meta["ref_header"]
    out_nii = nib.Nifti1Image(restored_labels, affine=ref_affine, header=ref_header)
    out_nii.set_data_dtype(np.uint8)
    nib.save(out_nii, output)

    elapsed = time.time() - start_time
    print(f"[NeuroScope 3D] Output successfully saved to: {output}")
    print(f"[NeuroScope 3D] Pipeline finished in {elapsed:.2f} seconds.")
    return output


def main():
    args = parse_args()
    try:
        run_pipeline(
            t1=args.t1,
            t1gd=args.t1gd,
            t2=args.t2,
            flair=args.flair,
            output=args.output,
            weights=args.weights,
            device=args.device,
            threshold=args.threshold,
        )
    except (PreprocessingError, PostprocessingError, FileNotFoundError, RuntimeError) as e:
        print(f"\n[NeuroScope 3D ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[NeuroScope 3D UNEXPECTED ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
