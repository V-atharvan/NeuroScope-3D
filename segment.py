"""
NeuroScope 3D - Standalone Segmentation CLI for Judges' Scorer
=============================================================
Usage:
    python segment.py --t1 <T1.nii.gz> --t1gd <T1Gd.nii.gz> --t2 <T2.nii.gz> --flair <FLAIR.nii.gz> --output <OUT.nii.gz>

Accepts four co-registered brain MRI sequences, runs the 3D segmentation pipeline,
and writes the predicted label map in BraTS 2021 integer codes (1 NCR, 2 ED, 4 ET)
preserving the input voxel grid and affine matrix.
"""
import sys
import os
import argparse
import nibabel as nib
import numpy as np

from inference.predict import run_pipeline, PreprocessingError, PostprocessingError


def parse_args():
    parser = argparse.ArgumentParser(
        description="NeuroScope 3D - 3D Brain MRI Segmentation CLI (Judges Scorer Entrypoint)"
    )
    parser.add_argument("--t1", required=True, help="Path to T1 native MRI (.nii or .nii.gz)")
    parser.add_argument("--t1gd", "--t1ce", required=True, dest="t1gd", help="Path to T1-Gd contrast enhanced MRI")
    parser.add_argument("--t2", required=True, help="Path to T2 weighted MRI")
    parser.add_argument("--flair", required=True, help="Path to FLAIR MRI")
    parser.add_argument("--output", "-o", required=True, help="Path to write predicted BraTS 2021 NIfTI mask")
    parser.add_argument("--weights", default=os.getenv("MODEL_WEIGHTS_PATH", "models/brats_mri_segmentation/models/model.pt"),
                        help="Path to pretrained model checkpoint")
    parser.add_argument("--device", default=os.getenv("MODEL_DEVICE", "cpu"),
                        help="PyTorch device ('cuda' or 'cpu')")
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 70)
    print("NeuroScope 3D — Research and Teaching Prototype Only")
    print("Not for clinical diagnosis, patient care, or surgical planning.")
    print("=" * 70)

    for seq_name, path in [("T1", args.t1), ("T1Gd", args.t1gd), ("T2", args.t2), ("FLAIR", args.flair)]:
        if not os.path.exists(path):
            print(f"Error: Missing input file for sequence {seq_name}: {path}", file=sys.stderr)
            sys.exit(1)

    print(f"Input Sequences:")
    print(f"  T1:    {args.t1}")
    print(f"  T1Gd:  {args.t1gd}")
    print(f"  T2:    {args.t2}")
    print(f"  FLAIR: {args.flair}")
    print(f"Output:  {args.output}")
    print(f"Device:  {args.device}")

    try:
        run_pipeline(
            t1_path=args.t1,
            t1gd_path=args.t1gd,
            t2_path=args.t2,
            flair_path=args.flair,
            output_path=args.output,
            weights_path=args.weights,
            device=args.device,
        )
        print(f"\n[SUCCESS] Predicted label map written to: {args.output}")

        # Verify output file
        if os.path.exists(args.output):
            out_nii = nib.load(args.output)
            labels = np.unique(np.asanyarray(out_nii.dataobj))
            print(f"Verified output dimensions: {out_nii.shape}")
            print(f"Unique label values: {sorted(labels.tolist())} (BraTS 2021: 0=BG, 1=NCR, 2=ED, 4=ET)")
        sys.exit(0)

    except (PreprocessingError, PostprocessingError, Exception) as e:
        print(f"\n[ERROR] Pipeline failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
