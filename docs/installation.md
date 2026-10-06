# Installation Guide — VisionPilot

## 1. Quick Start

### Option A: Windows Installer (Recommended)
1. Download **`VisionPilot-Setup-0.1.0.exe`** from the `release/` directory.
2. Double-click the installer.
3. Select whether to create a Desktop icon and click **Install**.
4. Launch VisionPilot from your Start Menu or Desktop.

### Option B: Portable ZIP
1. Download **`VisionPilot-0.1.0-portable.zip`**.
2. Right-click and choose **Extract All...** to any folder (e.g. `C:\Tools\VisionPilot`).
3. Open the extracted folder and double-click **`VisionPilot.exe`**.
4. The portable version automatically keeps all databases and logs inside the extracted folder.

---

## 2. Windows SmartScreen & Security Verification

VisionPilot release builds are currently unsigned open-source releases. When launching for the first time, Windows SmartScreen may display:

> "Windows protected your PC — Microsoft Defender SmartScreen prevented an unrecognized app from starting."

### To proceed:
1. Click **More info**.
2. Verify the publisher is listed as **VisionPilot Project**.
3. Click **Run anyway**.

You can verify the authenticity of your downloaded file before running by comparing its SHA-256 hash against `release/SHA256SUMS.txt`:

```powershell
Get-FileHash -Path .\VisionPilot-Setup-0.1.0.exe -Algorithm SHA256
```

Expected hash for v0.1.0:
```
aee0c21bad6e7011ae3fd1c20c5490b497c98ea6e87d1583ead470e1224e4e17
```

---

## 3. First Launch Checklist

On first launch:
1. VisionPilot conducts an automated device hardware audit.
2. The footer status bar will display your detected CPU, GPU, and NPU.
3. Ensure microphone access is permitted in **Windows Settings > Privacy & security > Microphone** if you plan to use voice commands.
4. Test by entering a simple command in the input box:
   ```
   Find the latest PDF in Downloads and show me where it is
   ```
