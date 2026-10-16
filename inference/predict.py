"""
NeuroScope 3D - Standalone Inference Entrypoint
Accepts 4 MRI sequence paths (T1, T1Gd, T2, FLAIR) and outputs a valid BraTS 2021 NIfTI mask.
"""
import argparse
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description="NeuroScope 3D Standalone Inference CLI. Research/teaching only."
    )
    parser.add_argument("--t1", required=True, help="Path to T1 NIfTI (.nii or .nii.gz)")
    parser.add_argument("--t1gd", required=True, help="Path to T1Gd (contrast) NIfTI (.nii or .nii.gz)")
    parser.add_argument("--t2", required=True, help="Path to T2 NIfTI (.nii or .nii.gz)")
    parser.add_argument("--flair", required=True, help="Path to FLAIR NIfTI (.nii or .nii.gz)")
    parser.add_argument("--output", required=True, help="Path to save output BraTS 2021 segmentation mask")
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"], help="Inference device")
    return parser.parse_args()


def run_pipeline(t1: str, t1gd: str, t2: str, flair: str, output: str, device: str = "cuda"):
    """
    Orchestrates preprocessing, model inference, postprocessing, and original grid restoration.
    """
    raise NotImplementedError(
        "Inference pipeline skeleton. Implementation in feature/ai-pipeline."
    )


def main():
    args = parse_args()
    print("NeuroScope 3D Inference CLI (Research and teaching prototype only)")
    try:
        run_pipeline(
            t1=args.t1,
            t1gd=args.t1gd,
            t2=args.t2,
            flair=args.flair,
            output=args.output,
            device=args.device,
        )
    except NotImplementedError as e:
        print(f"Status: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
