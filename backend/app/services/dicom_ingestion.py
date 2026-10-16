"""
NeuroScope 3D - Multi-File DICOM Series Ingestion Service
=========================================================
Ingests folders or ZIP archives of clinical DICOM (.dcm) slices,
de-identifies patient metadata, groups slices by SeriesInstanceUID,
sorts slices along the patient anatomical coordinate system,
constructs the physical NIfTI affine matrix, and converts 2D slices into 3D NIfTI volumes.
"""
from typing import Dict, Any, List, Tuple, Optional
import os
import zipfile
import shutil
import numpy as np
import nibabel as nib
import pydicom

from backend.app.services.validation import ValidationError


def classify_dicom_modality(series_description: str, protocol_name: str) -> Optional[str]:
    """Classifies DICOM series into BraTS target sequence codes."""
    combined = f"{series_description} {protocol_name}".lower()
    if any(k in combined for k in ["t1ce", "t1gd", "t1_ce", "t1+c", "t1_c", "post"]):
        return "t1gd"
    elif "flair" in combined or "t2_flair" in combined:
        return "flair"
    elif "t2" in combined:
        return "t2"
    elif "t1" in combined:
        return "t1"
    return None


def extract_dicom_series_to_nifti(
    dicom_files: List[str],
    output_dir: str
) -> Dict[str, str]:
    """
    Parses a collection of DICOM files, groups them into 3D series,
    constructs the spatial affine matrix, and writes NIfTI files (.nii.gz).
    Returns mapping of sequence_name -> nifti_file_path.
    """
    series_dict: Dict[str, List[pydicom.dataset.FileDataset]] = {}

    for fpath in dicom_files:
        try:
            dcm = pydicom.dcmread(fpath, stop_before_pixels=False, force=True)
            if not hasattr(dcm, "pixel_array") or not hasattr(dcm, "SeriesInstanceUID"):
                continue

            # Strip PHI attributes in-memory
            for phi_tag in ["PatientName", "PatientID", "PatientBirthDate", "PatientAddress", "InstitutionName"]:
                if hasattr(dcm, phi_tag):
                    setattr(dcm, phi_tag, "ANONYMIZED_RESEARCH_SUBJECT")

            uid = str(dcm.SeriesInstanceUID)
            if uid not in series_dict:
                series_dict[uid] = []
            series_dict[uid].append(dcm)
        except Exception:
            continue

    if not series_dict:
        raise ValidationError(
            "INVALID_DICOM",
            "No readable DICOM image slices with pixel data found in upload."
        )

    converted_paths: Dict[str, str] = {}

    for uid, slices in series_dict.items():
        if len(slices) < 2:
            continue

        first = slices[0]
        desc = getattr(first, "SeriesDescription", "")
        proto = getattr(first, "ProtocolName", "")
        modality = classify_dicom_modality(desc, proto)
        if not modality or modality in converted_paths:
            continue

        # Sort slices by distance along the normal vector
        try:
            iop = [float(x) for x in first.ImageOrientationPatient]
            row_vec = np.array(iop[:3])
            col_vec = np.array(iop[3:])
            normal_vec = np.cross(row_vec, col_vec)

            def slice_distance(ds):
                ipp = [float(x) for x in ds.ImagePositionPatient]
                return float(np.dot(ipp, normal_vec))

            sorted_slices = sorted(slices, key=slice_distance)
        except Exception:
            # Fallback sort by InstanceNumber or SliceLocation
            sorted_slices = sorted(slices, key=lambda s: getattr(s, "InstanceNumber", 0))

        # Stack 2D slice arrays into 3D volume (H, W, D)
        pixel_arrays = [s.pixel_array for s in sorted_slices]
        vol_data = np.stack(pixel_arrays, axis=-1).astype(np.float32)

        # Build Affine Matrix
        try:
            ps = [float(x) for x in first.PixelSpacing]  # [row_spacing, col_spacing]
            pos_first = np.array([float(x) for x in sorted_slices[0].ImagePositionPatient])
            pos_last = np.array([float(x) for x in sorted_slices[-1].ImagePositionPatient])

            slice_dir = (pos_last - pos_first) / float(len(sorted_slices) - 1)
            affine = np.eye(4, dtype=np.float32)
            affine[:3, 0] = row_vec * ps[0]
            affine[:3, 1] = col_vec * ps[1]
            affine[:3, 2] = slice_dir
            affine[:3, 3] = pos_first
        except Exception:
            affine = np.diag([1.0, 1.0, 1.0, 1.0])

        out_name = f"{modality}.nii.gz"
        out_path = os.path.join(output_dir, out_name)
        nii = nib.Nifti1Image(vol_data, affine)
        nib.save(nii, out_path)
        converted_paths[modality] = out_path

    return converted_paths


def process_dicom_archive(zip_path: str, extract_dir: str) -> Dict[str, str]:
    """Extracts a ZIP archive of DICOM slices and converts them to NIfTI."""
    raw_dir = os.path.join(extract_dir, "raw_dicom")
    os.makedirs(raw_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(raw_dir)

    all_files = []
    for root, _, files in os.walk(raw_dir):
        for f in files:
            all_files.append(os.path.join(root, f))

    converted = extract_dicom_series_to_nifti(all_files, output_dir=extract_dir)
    return converted
