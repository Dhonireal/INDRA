# Deployment & Release Guide — VisionPilot

## 1. Deployment Overview

VisionPilot offers two official deployment models:
1. **Windows Standard Installer (`VisionPilot-Setup-0.1.0.exe`):** Recommended for general desktop deployment. Integrates with the Windows Start Menu, creates optional Desktop shortcuts, and supports silent enterprise installation.
2. **Portable Distribution (`VisionPilot-0.1.0-portable.zip`):** Designed for zero-installation deployment, USB drives, or restricted enterprise environments where users cannot run installers.

---

## 2. Windows Installer Deployment

### Standard User Installation
Run `VisionPilot-Setup-0.1.0.exe` as any standard user account. Inno Setup defaults to `PrivilegesRequired=lowest`, installing into `%LOCALAPPDATA%\Programs\VisionPilot` without triggering UAC credential prompts.

### Silent / Enterprise Unattended Deployment
System administrators can deploy VisionPilot silently across a network using standard Inno Setup CLI parameters:

```powershell
VisionPilot-Setup-0.1.0.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-
```

To specify a custom destination directory:
```powershell
VisionPilot-Setup-0.1.0.exe /VERYSILENT /DIR="C:\EnterpriseApps\VisionPilot"
```

---

## 3. Uninstallation & Data Preservation Policy

When VisionPilot is uninstalled via Windows Settings or `unins000.exe`:
- **Removed:** All application binaries, Python dynamic libraries, Qt plugins, and Start Menu / Desktop shortcuts.
- **Preserved:** All user task history, completed action records, and audit logs residing in `%LOCALAPPDATA%\VisionPilot\data\visionpilot.db`.
- **Rationale:** Prevents accidental data loss of task history during version upgrades. Users wishing to purge all history can delete `%LOCALAPPDATA%\VisionPilot` manually or use the "Clear History" button within the application settings UI.

---

## 4. Upgrade Flow & Database Migration

Upgrading from Version A to Version B:
1. Running `VisionPilot-Setup-0.x.x.exe` overwrites the application binaries in-place.
2. Existing task history databases in `%LOCALAPPDATA%\VisionPilot\data\visionpilot.db` are retained intact.
3. On first launch of the upgraded application, `app.storage.database.init_db()` executes idempotent SQLite migrations (`CREATE TABLE IF NOT EXISTS`, indexing updates) safely inside a database transaction.
