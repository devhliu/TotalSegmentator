# runTotalSegmentatorLungLobes.py

import sys
import subprocess
from pathlib import Path

def main():
    """
    Run TotalSegmentator with specific parameters for MR segmentation
    
    Args:
        input_path: Path to the input DICOM or NIFTI file
        output_path: Path where to save the segmentation results
    """
    input_path = sys.argv[3]
    output_path = sys.argv[2]

    # Ensure paths are absolute
    input_path = Path(input_path).absolute()
    output_path = Path(output_path).absolute()
    output_type = sys.argv[4]

    # Check if output_type is valid
    if output_type not in ["dicom_seg", "dicom_rtstruct", "nifti"]:
        print(f"Error: Invalid output_type '{output_type}'. Must be 'dicom_seg', 'dicom_rtstruct', or 'nifti'.", file=sys.stderr)
        sys.exit(1)
    
    # Construct the command
    if output_type == "dicom_seg":
        cmd = [
            "TotalSegmentator",
            "-ot", "dicom_seg",
            "-ml",
            "-f",
            "-ta", "total",
            "-i", str(input_path),
            "-o", str(output_path)
        ]
    elif output_type == "dicom_rtstruct":
        cmd = [
            "TotalSegmentator",
            "-ot", "dicom_rtstruct",
            "-ml",
            "-f",
            "-ta", "total",
            "-i", str(input_path),
            "-o", str(output_path)
        ]
    elif output_type == "nifti":
        cmd = [
            "TotalSegmentator",
            "-ot", "nifti",
            "-ml",
            "-f",
            "-ta", "total",
            "-i", str(input_path),
            "-o", str(output_path)
        ]
    else:
        print(f"Error: Invalid output_type '{output_type}'. Must be 'dicom_seg', 'dicom_rtstruct', or 'nifti'.", file=sys.stderr)
        sys.exit(1)
    
    print(f"Running command: {' '.join(cmd)}")

    # Add a pause at the end of the script
    input("Press Enter to exit...")
    
    # Execute the command
    try:
        subprocess.run(cmd, check=True)
        print(f"Segmentation completed successfully. Results saved to {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error running TotalSegmentator: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

"""
    # Fix the warnings by explicitly setting transfer syntax parameters
    rtstruct.save(str(output_path), little_endian=True, implicit_vr=False)
"""

if __name__ == "__main__":
    main()