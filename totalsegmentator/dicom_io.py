import os
import shutil
import zipfile
import subprocess
import platform

from tqdm import tqdm

import numpy as np
import dicom2nifti
import pydicom

from totalsegmentator.config import get_weights_dir
from totalsegmentator.config import get_version

def command_exists(command):
    return shutil.which(command) is not None


def download_dcm2niix():
    import urllib.request
    print("  Downloading dcm2niix...")

    if platform.system() == "Windows":
        # url = "https://github.com/rordenlab/dcm2niix/releases/latest/download/dcm2niix_win.zip"
        url = "https://github.com/rordenlab/dcm2niix/releases/download/v1.0.20230411/dcm2niix_win.zip"
    elif platform.system() == "Darwin":  # Mac
        # raise ValueError("For MacOS automatic installation of dcm2niix not possible. Install it manually.")
        if platform.machine().startswith("arm") or platform.machine().startswith("aarch"):  # arm
            # url = "https://github.com/rordenlab/dcm2niix/releases/latest/download/macos_dcm2niix.pkg"
            url = "https://github.com/rordenlab/dcm2niix/releases/download/v1.0.20230411/dcm2niix_macos.zip"
        else:  # intel
            # unclear if this is the right link (is the same as for arm)
            # url = "https://github.com/rordenlab/dcm2niix/releases/latest/download/macos_dcm2niix.pkg"
            url = "https://github.com/rordenlab/dcm2niix/releases/download/v1.0.20230411/dcm2niix_macos.zip"
    elif platform.system() == "Linux":
        # url = "https://github.com/rordenlab/dcm2niix/releases/latest/download/dcm2niix_lnx.zip"
        url = "https://github.com/rordenlab/dcm2niix/releases/download/v1.0.20230411/dcm2niix_lnx.zip"
    else:
        raise ValueError("Unknown operating system. Can not download the right version of dcm2niix.")

    config_dir = get_weights_dir()

    urllib.request.urlretrieve(url, config_dir / "dcm2niix.zip")
    with zipfile.ZipFile(config_dir / "dcm2niix.zip", 'r') as zip_ref:
        zip_ref.extractall(config_dir)

    # Give execution permission to the script
    if platform.system() == "Windows":
        os.chmod(config_dir / "dcm2niix.exe", 0o755)
    else:
        os.chmod(config_dir / "dcm2niix", 0o755)

    # Clean up
    if (config_dir / "dcm2niix.zip").exists():
        os.remove(config_dir / "dcm2niix.zip")
    if (config_dir / "dcm2niibatch").exists():
        os.remove(config_dir / "dcm2niibatch")


def dcm_to_nifti_LEGACY(input_path, output_path, verbose=False):
    """
    Uses dcm2niix (does not properly work on windows)

    input_path: a directory of dicom slices
    output_path: a nifti file path
    """
    verbose_str = "" if verbose else "> /dev/null"

    config_dir = get_weights_dir()

    if command_exists("dcm2niix"):
        dcm2niix = "dcm2niix"
    else:
        if platform.system() == "Windows":
            dcm2niix = config_dir / "dcm2niix.exe"
        else:
            dcm2niix = config_dir / "dcm2niix"
        if not dcm2niix.exists():
            download_dcm2niix()

    subprocess.call(f"\"{dcm2niix}\" -o {output_path.parent} -z y -f {output_path.name[:-7]} {input_path} {verbose_str}", shell=True)

    if not output_path.exists():
        print(f"Content of dcm2niix output folder ({output_path.parent}):")
        print(list(output_path.parent.glob("*")))
        raise ValueError("dcm2niix failed to convert dicom to nifti.")

    nii_files = list(output_path.parent.glob("*.nii.gz"))

    if len(nii_files) > 1:
        print("WARNING: Dicom to nifti resulted in several nifti files. Skipping files which contain ROI in filename.")
        for nii_file in nii_files:
            # output file name is "converted_dcm.nii.gz" so if ROI in name, then this can be deleted
            if "ROI" in nii_file.name:
                os.remove(nii_file)
                print(f"Skipped: {nii_file.name}")

    nii_files = list(output_path.parent.glob("*.nii.gz"))

    if len(nii_files) > 1:
        print("WARNING: Dicom to nifti resulted in several nifti files. Only using first one.")
        print([f.name for f in nii_files])
        for nii_file in nii_files[1:]:
            os.remove(nii_file)
        # todo: have to rename first file to not contain any counter which is automatically added by dcm2niix

    os.remove(str(output_path)[:-7] + ".json")


def dcm_to_nifti(input_path, output_path, tmp_dir=None, verbose=False):
    """
    Uses dicom2nifti package (also works on windows)

    input_path: a directory of dicom slices or a zip file of dicom slices or a bytes object of zip file
    output_path: a nifti file path
    tmp_dir: extract zip file to this directory, else to the same directory as the zip file. Needs to be set if input is a zip file.
    """
    # Check if input_path is a zip file and extract it
    if zipfile.is_zipfile(input_path):
        if tmp_dir is None:
            raise ValueError("tmp_dir must be set when input_path is a zip file or bytes object of zip file")
        if verbose: print(f"Extracting zip file: {input_path}")
        extract_dir = os.path.splitext(input_path)[0] if tmp_dir is None else tmp_dir / "extracted_dcm"
        with zipfile.ZipFile(input_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            input_path = extract_dir
    
    # Convert to nifti
    dicom2nifti.dicom_series_to_nifti(input_path, output_path, reorient_nifti=True)


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


def save_mask_as_rtstruct(img_data, selected_classes, dcm_reference_file, output_path):
    """
    dcm_reference_file: a directory with dcm slices ??
    """
    from rt_utils import RTStructBuilder
    import logging
    logging.basicConfig(level=logging.WARNING)  # avoid messages from rt_utils

    # create new RT Struct - requires original DICOM
    rtstruct = RTStructBuilder.create_new(dicom_series_path=dcm_reference_file)

    # Rotate segmentation to match DICOM orientation
    img_data_rotated = np.rot90(img_data, 1, (0, 1))  # rotate segmentation in-plane

    # add mask to RT Struct
    for class_idx, class_name in tqdm(selected_classes.items()):
        binary_img = img_data_rotated == class_idx
        if class_name[0].islower(): continue  # skip first non upper character
        if binary_img.sum() > 0:  # only save none-empty images

            # add segmentation to RT Struct
            rtstruct.add_roi(
                mask=binary_img,  # has to be a binary numpy array
                name=class_name
            )

    # Save the RT Struct without unsupported keyword arguments
    rtstruct.save(str(output_path))


def save_mask_as_dicomseg(img_data, selected_classes, dcm_reference_file, output_path):
    """
    Creates a DICOM Segmentation object using highdicom
    
    Parameters
    ----------
    img_data: numpy.ndarray
        3D array with segmentation labels
    selected_classes: dict
        Dictionary mapping class indices to class names
    dcm_reference_file: str or Path
        Directory containing the source DICOM images
    output_path: str or Path
        Path where to save the DICOM SEG file
    """
    import highdicom as hd
    from pydicom.sr.codedict import codes

    import logging
    logging.basicConfig(level=logging.WARNING)  # avoid messages from highdicom
    
    try:
        # Load the original DICOM series
        dicom_series = load_dicom_series(dcm_reference_file)
        if not dicom_series:
            raise ValueError("No DICOM files found in the reference directory")
        
        # Create segment descriptions
        segment_descriptions = []
        
        # Track which segments are actually present in the data
        present_segments = {}
        
        # Rotate segmentation to match DICOM orientation
        img_data_rotated = np.rot90(img_data, 1, (0, 1))  # rotate segmentation in-plane

        # First pass: identify which segments are present in the data
        for class_idx, class_name in selected_classes.items():
            if class_idx == 0:  # Skip background
                continue
            
            if class_name[0].islower():
                continue

            # Create binary mask for this class
            binary_img = img_data_rotated == class_idx
            if binary_img.sum() > 0:  # only include non-empty segments
                present_segments[class_idx] = class_name
        
        # Second pass: create segment descriptions for present segments
        for segment_number, (class_idx, class_name) in enumerate(present_segments.items(), start=1):
            # Create segment description
            segment_descriptions.append(
                hd.seg.SegmentDescription(
                    segment_number=segment_number,
                    segment_label=class_name,
                    segmented_property_category=codes.cid7150.Tissue,
                    segmented_property_type=codes.cid7166.ConnectiveTissue,
                    algorithm_type=hd.seg.SegmentAlgorithmTypeValues.AUTOMATIC,
                    algorithm_identification=hd.AlgorithmIdentificationSequence(
                        name='TotalSegmentator',
                        version=get_version(),
                        family=codes.cid7162.ArtificialIntelligence
                    ),
                    tracking_uid=hd.UID(),
                    tracking_id='TotalSegmentator'
                )
            )
        
        # Create a multi-class segmentation array where each class has its own channel
        num_segments = len(segment_descriptions)
        if num_segments == 0:
            raise ValueError("No non-empty segments found in the segmentation data")
        
        # Create a binary multi-class segmentation array with correct dimensions
        # highdicom expects: (num_segments, num_frames, rows, columns)
        binary_seg_array = np.zeros((img_data_rotated.shape[2], img_data_rotated.shape[0], img_data_rotated.shape[1], num_segments), dtype=np.uint8)
        
        # Fill the binary segmentation array
        img_data_rotated_transposed = np.transpose(img_data_rotated, (2, 0, 1))     # Transpose to (frames, rows, columns)
        img_data_rotated_transposed = img_data_rotated_transposed[::-1, :, :]       # Flip the array to match DICOM orientation
        for i, (class_idx, _) in enumerate(present_segments.items()):
            # Convert to binary mask and transpose to match expected dimensions
            mask = np.zeros(img_data_rotated_transposed.shape, dtype=np.uint8)
            mask[img_data_rotated_transposed == class_idx] = 1
            binary_seg_array[:, :, :, i] = mask
        
        # Get metadata from reference image
        ref_image = dicom_series[0]
        series_instance_uid = hd.UID()
        
        # Get original series description and number
        original_series_description = ""
        original_series_number = 0
        
        if hasattr(ref_image, 'SeriesDescription'):
            original_series_description = ref_image.SeriesDescription
        if hasattr(ref_image, 'SeriesNumber'):
            original_series_number = ref_image.SeriesNumber
        
        # Create the Segmentation object
        seg_dataset = hd.seg.Segmentation(
            source_images=dicom_series,
            pixel_array=binary_seg_array,       # Shape: (num_segments, frames, rows, columns)
            segmentation_type=hd.seg.SegmentationTypeValues.BINARY,
            segment_descriptions=segment_descriptions,
            series_instance_uid=series_instance_uid,
            series_number=original_series_number,
            series_description=f"{original_series_description} Seg",
            sop_instance_uid=hd.UID(),
            instance_number=1,
            manufacturer='TotalSegmentator',
            manufacturer_model_name='TotalSegmentator',
            software_versions=get_version(),
            device_serial_number='1'
        )
        
        # Save the DICOM SEG file
        seg_dataset.save_as(output_path)
        
    except Exception as e:
        print(f"Error creating DICOM SEG: {e}")
        raise


def save_mask_as_dicomseg_PYDICOM(img_data, selected_classes, dcm_reference_file, output_path):
    """
    Creates a DICOM Segmentation object using pydicom
    
    Parameters
    ----------
    img_data: numpy.ndarray
        3D array with segmentation labels
    selected_classes: dict
        Dictionary mapping class indices to class names
    dcm_reference_file: str or Path
        Directory containing the source DICOM images
    output_path: str or Path
        Path where to save the DICOM SEG file
    """
    from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
    from pydicom.sequence import Sequence
    from pydicom.uid import generate_uid
    import datetime
    import logging
    
    logging.basicConfig(level=logging.WARNING)  # avoid messages
    
    try:
        # Load the original DICOM series
        dicom_series = load_dicom_series(dcm_reference_file)
        if not dicom_series:
            raise ValueError("No DICOM files found in the reference directory")
        
        # Get reference image
        ref_image = dicom_series[0]
        
        # Rotate segmentation to match DICOM orientation
        img_data_rotated = np.rot90(img_data, 1, (0, 1))  # rotate segmentation in-plane
        
        # Track which segments are actually present in the data
        present_segments = {}
        
        # First pass: identify which segments are present in the data
        for class_idx, class_name in selected_classes.items():
            if class_idx == 0:  # Skip background
                continue
            
            if class_name[0].islower():  # Filter out classes that don't start with uppercase
                continue
                
            # Create binary mask for this class
            binary_img = img_data_rotated == class_idx
            if binary_img.sum() > 0:  # only include non-empty segments
                present_segments[class_idx] = class_name
        
        if not present_segments:
            raise ValueError("No non-empty segments found in the segmentation data")
        
        # Create file meta information
        file_meta = FileMetaDataset()
        file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.66.4'  # Segmentation Storage
        file_meta.MediaStorageSOPInstanceUID = generate_uid()
        file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
        
        # Create the FileDataset instance
        seg_dataset = FileDataset(output_path, {}, file_meta=file_meta, preamble=b"\0" * 128)
        
        # Add the data elements
        seg_dataset.SOPClassUID = '1.2.840.10008.5.1.4.1.1.66.4'  # Segmentation Storage
        seg_dataset.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
        
        # Patient information (copy from reference image)
        for attr in ['PatientName', 'PatientID', 'PatientBirthDate', 'PatientSex']:
            if hasattr(ref_image, attr):
                setattr(seg_dataset, attr, getattr(ref_image, attr))
        
        # Study information (copy from reference image)
        for attr in ['StudyInstanceUID', 'StudyID', 'StudyDate', 'StudyTime', 'AccessionNumber']:
            if hasattr(ref_image, attr):
                setattr(seg_dataset, attr, getattr(ref_image, attr))
        
        # Series information
        seg_dataset.SeriesInstanceUID = generate_uid()
        
        # Get original series description and number
        original_series_description = ""
        original_series_number = 0
        
        if hasattr(ref_image, 'SeriesDescription'):
            original_series_description = ref_image.SeriesDescription
        if hasattr(ref_image, 'SeriesNumber'):
            original_series_number = ref_image.SeriesNumber
        
        seg_dataset.SeriesDescription = f"{original_series_description} Seg"
        seg_dataset.SeriesNumber = original_series_number
        
        # Instance information
        seg_dataset.InstanceNumber = 1
        
        # Current date and time
        dt = datetime.datetime.now()
        seg_dataset.ContentDate = dt.strftime('%Y%m%d')
        seg_dataset.ContentTime = dt.strftime('%H%M%S.%f')[:-3]
        
        # Segmentation specific attributes
        seg_dataset.SegmentationType = 'BINARY'
        seg_dataset.SegmentationFractionalType = 'PROBABILITY'
        seg_dataset.MaximumFractionalValue = 1
        
        # Dimension Organization
        seg_dataset.DimensionOrganizationType = 'TILED_FULL'
        
        # Create Segment Sequence
        segment_sequence = []
        for segment_number, (class_idx, class_name) in enumerate(present_segments.items(), start=1):
            segment = Dataset()
            segment.SegmentNumber = segment_number
            segment.SegmentLabel = class_name
            segment.SegmentAlgorithmType = 'AUTOMATIC'
            segment.SegmentAlgorithmName = 'TotalSegmentator'
            
            # Segmented Property Category Code Sequence
            category_code = Dataset()
            category_code.CodeValue = 'T-D0050'
            category_code.CodingSchemeDesignator = 'SRT'
            category_code.CodeMeaning = 'Tissue'
            segment.SegmentedPropertyCategoryCodeSequence = Sequence([category_code])
            
            # Segmented Property Type Code Sequence
            type_code = Dataset()
            type_code.CodeValue = 'T-D0050'
            type_code.CodingSchemeDesignator = 'SRT'
            type_code.CodeMeaning = class_name
            segment.SegmentedPropertyTypeCodeSequence = Sequence([type_code])
            
            segment_sequence.append(segment)
        
        seg_dataset.SegmentSequence = Sequence(segment_sequence)
        
        # Create binary segmentation data
        # Transpose to match DICOM orientation
        img_data_rotated_transposed = np.transpose(img_data_rotated, (2, 0, 1))  # (frames, rows, columns)
        img_data_rotated_transposed = img_data_rotated_transposed[::-1, :, :]    # Flip to match DICOM orientation
        
        # Create binary masks for each segment
        binary_masks = []
        for class_idx in present_segments.keys():
            mask = np.zeros(img_data_rotated_transposed.shape, dtype=np.uint8)
            mask[img_data_rotated_transposed == class_idx] = 1
            binary_masks.append(mask)
        
        # Combine all masks into a single array
        combined_mask = np.zeros(img_data_rotated_transposed.shape, dtype=np.uint8)
        for i, mask in enumerate(binary_masks, start=1):
            combined_mask[mask == 1] = i
        
        # Set pixel data
        seg_dataset.NumberOfFrames = combined_mask.shape[0]
        seg_dataset.Rows = combined_mask.shape[1]
        seg_dataset.Columns = combined_mask.shape[2]
        seg_dataset.BitsAllocated = 8
        seg_dataset.BitsStored = 8
        seg_dataset.HighBit = 7
        seg_dataset.PixelRepresentation = 0
        seg_dataset.SamplesPerPixel = 1
        
        # Flatten the array and convert to bytes
        pixel_data = combined_mask.tobytes()
        seg_dataset.PixelData = pixel_data
        
        # Reference the source images
        shared_functional_groups_sequence = Dataset()
        
        # Derivation Image Sequence
        derivation_image_sequence = []
        for dcm in dicom_series:
            derivation_image = Dataset()
            derivation_image.ReferencedSOPClassUID = dcm.SOPClassUID
            derivation_image.ReferencedSOPInstanceUID = dcm.SOPInstanceUID
            derivation_image_sequence.append(derivation_image)
        
        shared_functional_groups_sequence.DerivationImageSequence = Sequence(derivation_image_sequence)
        seg_dataset.SharedFunctionalGroupsSequence = Sequence([shared_functional_groups_sequence])
        
        # Per-frame Functional Groups Sequence
        per_frame_functional_groups_sequence = []
        for frame_idx in range(seg_dataset.NumberOfFrames):
            frame_content = Dataset()
            frame_content.FrameContentSequence = Sequence([Dataset()])
            per_frame_functional_groups_sequence.append(frame_content)
        
        seg_dataset.PerFrameFunctionalGroupsSequence = Sequence(per_frame_functional_groups_sequence)
        
        # Save the DICOM SEG file
        # Use little_endian and implicit_vr arguments to suppress warnings and ensure compatibility
        seg_dataset.save_as(output_path, write_like_original=False, little_endian=True, implicit_vr=False)
        
    except Exception as e:
        print(f"Error creating DICOM SEG: {e}")
        raise