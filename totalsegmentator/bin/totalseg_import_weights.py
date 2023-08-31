#!/usr/bin/env python
import os
import sys
from pathlib import Path
import argparse
import zipfile

from totalsegmentator.config import get_totalseg_dir


def main():
    """
    Import manually downloaded weights (zip file) to the right folder.
    """
    parser = argparse.ArgumentParser(description="Import manually downloaded weights.",
                                     epilog="Written by Jakob Wasserthal.")

    parser.add_argument("-i", "--weights_file",
                        help="path to the weights zip file", 
                        type=lambda p: Path(p).absolute(), required=True)
    parser.add_argument("-t", "--model_type", choices=["3d_fullres", "3d_lowres", "2d"],
                        help="Type of model", default="3d_fullres")

    args = parser.parse_args()

    # Get config dir
    if "TOTALSEG_WEIGHTS_PATH" in os.environ:
        config_dir = Path(os.environ["TOTALSEG_WEIGHTS_PATH"]) / "nnUNet"
    else:
        totalseg_dir = get_totalseg_dir()
        config_dir = totalseg_dir / "nnunet/results/nnUNet"
    (config_dir / "3d_fullres").mkdir(exist_ok=True, parents=True)
    (config_dir / "3d_lowres").mkdir(exist_ok=True, parents=True)
    (config_dir / "2d").mkdir(exist_ok=True, parents=True)

    config_dir = config_dir / args.model_type

    print(f"Extracting file {args.weights_file} to {config_dir}")

    with zipfile.ZipFile(args.weights_file, 'r') as zip_f:
        zip_f.extractall(config_dir)


if __name__ == "__main__":
    main()