#!/usr/bin/env python
import argparse
import os
import tempfile
from pathlib import Path
import time
import numpy as np
import nibabel as nib
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import generate_uid
import highdicom as hd
from highdicom.seg import Segmentation

from totalsegmentator.python_api import totalsegmentator
from totalsegmentator.dicom_io import dcm_to_nifti
from totalsegmentator.map_to_binary import class_map
from totalsegmentator.config import get_version


def load_dicom_series(dicom_dir):
    """Load all DICOM files from a directory and sort them by instance number."""
    dicom_files = []
    supported_modalities = [
        'CT Image Storage',
        'MR Image Storage',
        'Positron Emission Tomography Image Storage',
        'Nuclear Medicine Image Storage'  # For SPECT
    ]
    
    for root, _, files in os.walk(dicom_dir):
        for file in files:
            try:
                dicom_path = os.path.join(root, file)
                dcm = pydicom.dcmread(dicom_path, force=True)
                if hasattr(dcm, 'SOPClassUID') and dcm.SOPClassUID.name in supported_modalities:
                    dicom_files.append(dcm)
            except:
                pass
    
    if not dicom_files:
        raise ValueError("No supported DICOM files found. Supported modalities: CT, MR, PET, SPECT")
    
    # Sort by instance number
    dicom_files.sort(key=lambda x: int(x.InstanceNumber))
    return dicom_files


def create_dicom_segmentation(segmentation_array, dicom_series, class_dict, output_path):
    """
    Create a DICOM Segmentation object from a segmentation array.
    
    Args:
        segmentation_array: 3D numpy array with segmentation labels
        dicom_series: List of DICOM datasets from the original series
        class_dict: Dictionary mapping segment numbers to segment names
        output_path: Path to save the DICOM SEG file
    """
    # Create segment descriptions
    segment_descriptions = []
    
    for segment_number, segment_name in class_dict.items():
        if segment_number == 0:  # Skip background
            continue
            
        # Check if this segment exists in the segmentation
        if segment_number in np.unique(segmentation_array):
            segment_descriptions.append(
                hd.seg.SegmentDescription(
                    segment_number=segment_number,
                    segment_label=segment_name,
                    segmented_property_category=hd.seg.SegmentedPropertyCategory.TISSUE,
                    segmented_property_type=hd.seg.SegmentedPropertyType.TISSUE
                )
            )
    
    # Get original series description and number
    original_series_description = ""
    original_series_number = 0
    
    # Try to get series description and number from the first DICOM file
    if dicom_series and len(dicom_series) > 0:
        if hasattr(dicom_series[0], 'SeriesDescription'):
            original_series_description = dicom_series[0].SeriesDescription
        if hasattr(dicom_series[0], 'SeriesNumber'):
            original_series_number = dicom_series[0].SeriesNumber
    
    # Create new series description and number
    new_series_description = f"{original_series_description} Seg"
    new_series_number = original_series_number + 1000
    
    # Create the Segmentation object
    seg_dataset = Segmentation(
        source_images=dicom_series,
        pixel_array=segmentation_array,
        segmentation_type=hd.seg.SegmentationTypeValues.BINARY,
        segment_descriptions=segment_descriptions,
        series_instance_uid=generate_uid(),
        series_number=new_series_number,
        series_description=new_series_description,
        sop_instance_uid=generate_uid(),
        instance_number=1,
        manufacturer='TotalSegmentator',
        manufacturer_model_name='TotalSegmentator',
        software_versions=get_version(),
        device_serial_number='1'
    )
    
    # Save the DICOM SEG file
    seg_dataset.save_as(output_path)
    
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Process DICOM series and output DICOM Segmentation object.",
                                     epilog="Based on TotalSegmentator by Jakob Wasserthal.")

    parser.add_argument("-i", metavar="directory", dest="input",
                        help="Directory containing DICOM series",
                        type=lambda p: Path(p).absolute(), required=True)

    parser.add_argument("-o", metavar="filepath", dest="output",
                        help="Output DICOM Segmentation file",
                        type=lambda p: Path(p).absolute(), required=True)

    parser.add_argument("-f", "--fast", action="store_true", help="Run faster lower resolution model (3mm)",
                        default=False)

    parser.add_argument("-ff", "--fastest", action="store_true", help="Run even faster lower resolution model (6mm)",
                        default=False)

    parser.add_argument("-ta", "--task", choices=["total", "body", "body_mr", "vertebrae_mr",
                        "lung_vessels", "cerebral_bleed", "hip_implant", "coronary_arteries",
                        "pleural_pericard_effusion", "test",
                        "appendicular_bones", "appendicular_bones_mr", "tissue_types", "heartchambers_highres",
                        "face", "vertebrae_body", "total_mr", "tissue_types_mr", "tissue_4_types", "face_mr",
                        "head_glands_cavities", "head_muscles", "headneck_bones_vessels", "headneck_muscles",
                        "brain_structures", "liver_vessels", "oculomotor_muscles",
                        "thigh_shoulder_muscles", "thigh_shoulder_muscles_mr", "lung_nodules", "kidney_cysts", 
                        "breasts", "ventricle_parts", "aortic_sinuses", "liver_segments", "liver_segments_mr"],
                        help="Select which model to use. This determines what is predicted.",
                        default="total")

    parser.add_argument("-rs", "--roi_subset", type=str, nargs="+",
                        help="Define a subset of classes to save (space separated list of class names).")

    parser.add_argument("-d", "--device", choices=["gpu", "cpu", "mps"], help="Device to run on (default: gpu).",
                        default="gpu")

    parser.add_argument("-v", "--verbose", action="store_true", help="Show more intermediate output",
                        default=False)

    args = parser.parse_args()

    # Create temporary directory for intermediate files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        
        if args.verbose:
            print(f"Created temporary directory: {temp_dir_path}")
        
        # Convert DICOM to NIFTI
        if args.verbose:
            print("Converting DICOM to NIFTI...")
        
        nifti_path = temp_dir_path / "input.nii.gz"
        dcm_to_nifti(args.input, nifti_path, tmp_dir=temp_dir_path, verbose=args.verbose)
        
        # Run TotalSegmentator
        if args.verbose:
            print("Running TotalSegmentator...")
        
        seg_output_path = temp_dir_path / "segmentations.nii.gz"
        
        # Run with multilabel output
        segmentation, _ = totalsegmentator(
            nifti_path, 
            seg_output_path, 
            ml=True,
            fast=args.fast,
            fastest=args.fastest,
            task=args.task,
            roi_subset=args.roi_subset,
            device=args.device,
            quiet=not args.verbose,
            verbose=args.verbose,
            skip_saving=False
        )
        
        # Load the segmentation result
        if args.verbose:
            print("Loading segmentation results...")
        
        seg_img = nib.load(seg_output_path)
        seg_data = seg_img.get_fdata().astype(np.uint8)
        
        # Load the original DICOM series
        if args.verbose:
            print("Loading original DICOM series...")
        
        dicom_series = load_dicom_series(args.input)
        
        # Get the class mapping
        if args.roi_subset:
            # Create a subset of the class map
            selected_classes = {i+1: roi for i, roi in enumerate(args.roi_subset)}
        else:
            # Use all classes from the task
            selected_classes = {i+1: class_name for i, class_name in enumerate(class_map[args.task].values())}
        
        # Create DICOM Segmentation object
        if args.verbose:
            print("Creating DICOM Segmentation object...")
        
        create_dicom_segmentation(seg_data, dicom_series, selected_classes, args.output)
        
        if args.verbose:
            print(f"DICOM Segmentation saved to: {args.output}")


if __name__ == "__main__":
    main()