import sys
import os
import platform
import subprocess
import shutil
import json

def run_cmd(cmd):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return res.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def main():
    print("=== BASIC SYSTEM AUDIT ===")
    print(f"Platform: {platform.platform()}")
    print(f"Machine: {platform.machine()}")
    print(f"Processor: {platform.processor()}")
    print(f"Architecture: {platform.architecture()}")
    print(f"Python Executable: {sys.executable}")
    print(f"Python Version: {sys.version}")
    print(f"Python Build: {platform.python_build()}")
    print(f"Python Compiler: {platform.python_compiler()}")

    print("\n=== SYSTEM MEMORY & DISK ===")
    total, used, free = shutil.disk_usage("C:\\")
    print(f"Drive C: Total: {total // (2**30)} GB, Used: {used // (2**30)} GB, Free: {free // (2**30)} GB")

    print("\n=== HARDWARE VIA POWERSHELL WMI ===")
    ps_script = """
    $os = Get-CimInstance Win32_OperatingSystem
    $cs = Get-CimInstance Win32_ComputerSystem
    $cpu = Get-CimInstance Win32_Processor
    $gpu = Get-CimInstance Win32_VideoController
    $pnp = Get-PnpDevice | Where-Object { $_.FriendlyName -match 'NPU|Neural|Hexagon|Qualcomm|ComputeAccelerator' } | Select-Object FriendlyName, Status, Class, DeviceID

    [PSCustomObject]@{
        OS = $os.Caption
        OSVersion = $os.Version
        OSBuild = $os.BuildNumber
        Manufacturer = $cs.Manufacturer
        Model = $cs.Model
        SystemType = $cs.SystemType
        RAM_Bytes = $cs.TotalPhysicalMemory
        CPU_Name = $cpu.Name
        CPU_Cores = $cpu.NumberOfCores
        CPU_Logical = $cpu.NumberOfLogicalProcessors
        GPU_Name = ($gpu | ForEach-Object { $_.Name }) -join '; '
        GPU_Driver = ($gpu | ForEach-Object { $_.DriverVersion }) -join '; '
        NPU_Devices = ($pnp | ForEach-Object { "$($_.FriendlyName) [Status: $($_.Status), Class: $($_.Class), ID: $($_.DeviceID)]" })
    } | ConvertTo-Json -Depth 3
    """
    wmi_json = run_cmd(f'powershell -Command "{ps_script}"')
    print("Hardware JSON:")
    print(wmi_json)

    print("\n=== AI RUNTIMES & PACKAGES TEST ===")
    for pkg in ["pyside6", "pyqt6", "onnxruntime", "onnxruntime-directml", "onnxruntime-qnn", "torch", "sounddevice", "pyaudio", "pytesseract", "winsdk", "winrt", "pytest"]:
        pip_check = run_cmd(f'"{sys.executable}" -m pip index versions {pkg}')
        # If pip index doesn't work, test with pip cache or dry run install
        dry_run = run_cmd(f'"{sys.executable}" -m pip install --dry-run {pkg}')
        has_wheel = "Would install" in dry_run
        print(f"Package '{pkg}': {'Available' if has_wheel else 'Check dry-run'}")
        if not has_wheel:
            # show snippet of dry run output
            lines = [l for l in dry_run.splitlines() if "ERROR:" in l or "Could not find" in l or "Would install" in l]
            print(f"   -> Details: {lines[:2]}")

if __name__ == "__main__":
    main()
