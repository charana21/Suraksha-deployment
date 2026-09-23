# CrowdVision Packaging & Deployment Guide

## Overview
This guide explains how to package the CrowdVision backend into a single Linux executable (binary) that includes all dependencies and models.

## Prerequisites
- **Target OS**: The build **MUST** be performed on a Linux machine (or WSL/Docker) to produce a Linux executable. You cannot build a Linux binary directly from Windows.
- **Python**: Python 3.10+ installed.

## Build Instructions (On Linux/WSL)

1.  **Transfer source code** to the Linux machine.
2.  **Navigate** to the project root.
3.  **Run the build script**:
    ```bash
    chmod +x build_linux.sh
    ./build_linux.sh
    ```
    This script will:
    - Install `pyinstaller` and dependencies.
    - Bundle `yolov8s.pt` and PET (`SHA_model.pth`) weights.
    - Create a single binary at `dist/crowdvision`.

## Deployment Instructions

1.  **Prepare Directory**:
    ```bash
    sudo mkdir -p /opt/crowdvision
    ```

2.  **Install Binary**:
    ```bash
    sudo cp dist/crowdvision /opt/crowdvision/
    sudo chmod +x /opt/crowdvision/crowdvision
    ```

3.  **Setup Configuration (Optional)**:
    - The binary has embedded defaults.
    - To override, place a `.env` file in `/opt/crowdvision/.env`.
    - **Note**: Systemd environment variables take precedence over `.env`.

4.  **Install Systemd Service**:
    ```bash
    sudo cp packaging/crowdvision.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now crowdvision
    ```

5.  **View Logs**:
    ```bash
    journalctl -u crowdvision -f
    ```

## Files Explained
- `packaging/crowdvision-linux.spec`: PyInstaller configuration file defining what to bundle.
- `packaging/crowdvision.service`: Systemd service definition.
- `build_linux.sh`: Automated build script.
