# runTotalSegmentatorLungLobes.py

import sys
import subprocess
from pathlib import Path
import argparse

def main():
    """
    Run TotalSegmentator with specific parameters for lung lobes segmentation
    """
    parser = argparse.ArgumentParser(description="Run TotalSegmentator with specific parameters for lung lobes segmentation")
    parser.add_argument("input_folder", help="Path to the input DICOM or NIFTI file")
    parser.add_argument("output_path", help="Path where to save the segmentation results")
    parser.add_argument("-ot", "--output_type", choices=["dicom_seg", "dicom_rtstruct", "nifti"], 
                        required=True, help="Output type: dicom_seg, dicom_rtstruct, or nifti")
    
    args = parser.parse_args()
    
    input_path = args.input_folder
    output_path = args.output_path
    output_type = args.output_type

    # Ensure paths are absolute
    input_path = Path(input_path).absolute()
    output_path = Path(output_path).absolute()
    
    # Construct the command
    cmd = [
        "TotalSegmentator",
        "-ot", output_type,
        "-ml",
        "-f",
        "-ta", "total",
        "-i", str(input_path),
        "-o", str(output_path)
    ]
    
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