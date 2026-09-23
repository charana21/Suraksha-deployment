#!/usr/bin/env python3
"""
CrowdVision Configuration Validator

Validates configuration files and checks system requirements before deployment.

Usage:
    python validate_config.py [--env-file PATH]

Exit codes:
    0 = All checks passed
    1 = Validation errors found
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Tuple
import logging
logger = logging.getLogger(__name__)

def print_header(title: str):
    """Print a section header."""
    logger.info("\n" + "=" * 60)
    logger.info(f"  {title}")
    logger.info("=" * 60)


def print_check(name: str, passed: bool, message: str = ""):
    """Print a check result."""
    status = "[OK]" if passed else "[!!]"
    logger.info(f"  {status} {name}")
    if message and not passed:
        logger.info(f"       {message}")


def validate_env_file(env_path: str) -> Tuple[bool, List[str]]:
    """Validate environment file exists and has required settings."""
    errors = []

    if not os.path.exists(env_path):
        errors.append(f"Environment file not found: {env_path}")
        return False, errors

    # Read env file
    env_vars = {}
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()

    # Required settings
    required = ["MONGODB_URI", "DEVICE"]
    for key in required:
        if key not in env_vars:
            errors.append(f"Missing required setting: {key}")

    # Validate specific settings
    if "DEVICE" in env_vars:
        device = env_vars["DEVICE"].lower()
        if device not in ["cuda", "cpu"]:
            errors.append(f"Invalid DEVICE value: {device} (must be 'cuda' or 'cpu')")

    if "LOG_LEVEL" in env_vars:
        level = env_vars["LOG_LEVEL"].upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if level not in valid_levels:
            errors.append(f"Invalid LOG_LEVEL: {level}")

    return len(errors) == 0, errors


def validate_directories(base_path: str) -> Tuple[bool, List[str]]:
    """Validate required directories exist and are writable."""
    errors = []

    required_dirs = [
        "data/uploads",
        "data/outputs",
        "data/heatmaps",
        "data/analytics",
        "data/images",
    ]

    for dir_name in required_dirs:
        dir_path = os.path.join(base_path, dir_name)
        if not os.path.exists(dir_path):
            errors.append(f"Directory missing: {dir_path}")
        elif not os.access(dir_path, os.W_OK):
            errors.append(f"Directory not writable: {dir_path}")

    return len(errors) == 0, errors


def validate_model_weights(base_path: str) -> Tuple[bool, List[str]]:
    """Validate ML model weights are present."""
    errors = []
    warnings = []

    # Check for YOLO model
    yolo_paths = [
        os.path.join(base_path, "weights", "yolov8n.pt"),
        os.path.join(base_path, "yolov8n.pt"),
    ]
    yolo_found = any(os.path.exists(p) for p in yolo_paths)
    if not yolo_found:
        warnings.append("YOLO model not found (will be auto-downloaded)")

    # Check for PET model
    pet_paths = [
        os.path.join(base_path, "data", "weights", "SHA_model.pth"),
        os.path.join(base_path, "weights", "SHA_model.pth"),
    ]
    pet_found = any(os.path.exists(p) for p in pet_paths)
    if not pet_found:
        warnings.append("PET model (SHA_model.pth) not found in data/weights/")

    # Print warnings
    for warning in warnings:
        logger.info(f"  [--] {warning}")

    return True, errors  # Warnings don't fail validation


def validate_gpu() -> Tuple[bool, List[str]]:
    """Validate GPU availability."""
    errors = []

    try:
        import torch

        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            for i in range(device_count):
                props = torch.cuda.get_device_properties(i)
                memory_gb = props.total_memory / (1024**3)
                logger.info(f"  [OK] GPU {i}: {props.name} ({memory_gb:.1f} GB)")

                if memory_gb < 4:
                    errors.append(f"GPU {i} has less than 4GB memory (may cause OOM)")
        else:
            logger.info("  [--] No CUDA GPU available (will use CPU)")
    except ImportError:
        errors.append("PyTorch not installed")

    return len(errors) == 0, errors


def validate_mongodb() -> Tuple[bool, List[str]]:
    """Validate MongoDB connection."""
    errors = []

    try:
        from pymongo import MongoClient
        from pymongo.errors import ConnectionFailure

        # Try to connect
        uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)

        # Ping the server
        client.admin.command("ping")
        logger.info(f"  [OK] MongoDB connected: {uri}")

        # Check database
        db_name = os.environ.get("MONGODB_DATABASE", "crowdvision")
        db = client[db_name]
        collections = db.list_collection_names()
        logger.info(f"  [OK] Database '{db_name}' has {len(collections)} collections")

        client.close()
    except ImportError:
        errors.append("pymongo not installed")
    except ConnectionFailure as e:
        errors.append(f"MongoDB connection failed: {e}")
    except Exception as e:
        errors.append(f"MongoDB error: {e}")

    return len(errors) == 0, errors


def validate_python_deps() -> Tuple[bool, List[str]]:
    """Validate Python dependencies are installed."""
    errors = []

    required_packages = [
        ("torch", "PyTorch"),
        ("torchvision", "TorchVision"),
        ("cv2", "OpenCV"),
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("motor", "Motor (MongoDB async)"),
        ("pydantic", "Pydantic"),
        ("numpy", "NumPy"),
    ]

    for module, name in required_packages:
        try:
            __import__(module)
            logger.info(f"  [OK] {name}")
        except ImportError:
            errors.append(f"Missing package: {name} ({module})")
            logger.info(f"  [!!] {name} - NOT INSTALLED")

    return len(errors) == 0, errors


def main():
    parser = argparse.ArgumentParser(description="Validate CrowdVision configuration")
    parser.add_argument(
        "--env-file", type=str, default=".env", help="Path to environment file"
    )
    parser.add_argument(
        "--base-path",
        type=str,
        default=None,
        help="Base path to CrowdVision installation",
    )
    args = parser.parse_args()

    # Determine base path
    if args.base_path:
        base_path = args.base_path
    else:
        # Assume script is in scripts/ directory
        base_path = str(Path(__file__).parent.parent)

    logger.info("\n" + "=" * 60)
    logger.info("  CROWDVISION CONFIGURATION VALIDATOR")
    logger.info("=" * 60)
    logger.info(f"\n  Base path: {base_path}")
    logger.info(f"  Env file: {args.env_file}")

    all_passed = True
    all_errors = []

    # Load environment file for subsequent checks
    env_path = (
        args.env_file
        if os.path.isabs(args.env_file)
        else os.path.join(base_path, args.env_file)
    )
    if os.path.exists(env_path):
        from dotenv import load_dotenv

        load_dotenv(env_path)

    # Run validations
    logger.info("Validating Environment File")
    passed, errors = validate_env_file(env_path)
    logger.info(f"Environment file validation: {'PASSED' if passed else 'FAILED'}")
    for e in errors:
        logger.info(f"       {e}")
    all_passed &= passed
    all_errors.extend(errors)

    logger.info("Validating Directory Structure")
    passed, errors = validate_directories(base_path)
    logger.info(f"Required directories validation: {'PASSED' if passed else 'FAILED'}")
    for e in errors:
        logger.info(f"       {e}")
    all_passed &= passed
    all_errors.extend(errors)

    logger.info("Validating Model Weights")
    passed, errors = validate_model_weights(base_path)
    # Don't fail on missing weights (auto-download)
    all_errors.extend(errors)

    logger.info("Validating Python Dependencies")
    passed, errors = validate_python_deps()
    all_passed &= passed
    all_errors.extend(errors)

    logger.info("Validating GPU Status")
    passed, errors = validate_gpu()
    # Don't fail on GPU issues (can use CPU)
    all_errors.extend(errors)

    logger.info("Validating MongoDB Connection")
    passed, errors = validate_mongodb()
    all_passed &= passed
    all_errors.extend(errors)

    # Summary
    logger.info("\n" + "=" * 60)
    if all_passed:
        logger.info("  VALIDATION PASSED - Ready for deployment")
    else:
        logger.info("  VALIDATION FAILED - Fix errors before deployment")
        logger.info("\n  Errors:")
        for error in all_errors:
            logger.info(f"    - {error}")
    logger.info("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
