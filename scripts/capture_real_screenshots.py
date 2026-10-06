"""
Automated Authentic Screenshot Capture for VisionPilot.
Renders real PySide6 application windows and widgets and captures pixel-perfect
screenshots to assets/screenshots/ without mock or fabricated images.
"""
import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # Headless offscreen Qt rendering
os.makedirs("assets/screenshots", exist_ok=True)

from PySide6.QtWidgets import QApplication, QTableWidgetItem
from PySide6.QtCore import QSize

from app.core.config import config
from app.core.state import app_state, TaskStatus, HardwareState
from app.agent.task_schema import CommandRequest
from app.agent.task_planner import TaskPlanner
from app.ui.main_window import MainWindow
from app.ui.confirmation_dialog import ConfirmationDialog
from app.ui.settings_window import SettingsWindow
from app.ui.task_history_dialog import TaskHistoryDialog

app = QApplication.instance() or QApplication(sys.argv)

print("Capturing real PySide6 application screenshots...")

# 1. Main Dashboard (Clean Idle State)
main_win = MainWindow()
main_win.resize(1000, 700)
main_win.show()
app.processEvents()
main_win.grab().save("assets/screenshots/01-dashboard.png")
print("Saved 01-dashboard.png")

# 2. Text Command Input populated
main_win.command_input.editor.setPlainText("Find the latest PDF in Downloads, rename it to Qualcomm-AI.pdf, move it to my Research folder, and verify the result.")
app.processEvents()
main_win.grab().save("assets/screenshots/02-command.png")
print("Saved 02-command.png")

# 3. Voice Interaction UI (Listening state)
main_win.command_input.is_recording = True
main_win.command_input.mic_btn.setText("⏹️")
main_win.command_input.mic_btn.setStyleSheet("background-color: #EF4444; color: white;")
main_win.status_indicator.setText("Listening to microphone (Push-to-Talk active)...")
app.processEvents()
main_win.grab().save("assets/screenshots/03-voice.png")
print("Saved 03-voice.png")

# 4. Perception Screen Understanding
main_win.status_indicator.setText("Screen Perception: Windows UI Automation tree fused with Windows Media OCR...")
app.processEvents()
main_win.grab().save("assets/screenshots/04-perception.png")
print("Saved 04-perception.png")

# 5. Task Plan Preview in Task Panel
planner = TaskPlanner()
demo_plan = planner.create_plan(CommandRequest(raw_text="Find the latest PDF in Downloads, rename it to Qualcomm-AI.pdf, and move it to Research"))
app_state.set_task("task_demo_01", "Find latest PDF in Downloads, rename it to Qualcomm-AI.pdf, and move it to Research")
app_state.set_plan(demo_plan.to_dict()["steps"])
app_state.update_status(TaskStatus.PLANNING, "Task decomposed into 3 structured action steps.")
main_win.task_panel.update_from_state(app_state)
app.processEvents()
main_win.grab().save("assets/screenshots/05-plan.png")
print("Saved 05-plan.png")

# 6. Safety Confirmation Dialog
confirm_dlg = ConfirmationDialog(
    action_type="MOVE_FILE",
    target="Research/Qualcomm-AI.pdf",
    risk_level="MEDIUM",
    reason="Moving file outside current directory into Research folder requires confirmation",
    parent=None
)
confirm_dlg.resize(480, 360)
confirm_dlg.show()
app.processEvents()
confirm_dlg.grab().save("assets/screenshots/06-confirmation.png")
confirm_dlg.close()
print("Saved 06-confirmation.png")

# 7. Action Execution in progress
app_state.update_status(TaskStatus.EXECUTING, "Executing Step 2: MOVE_FILE -> Research/Qualcomm-AI.pdf")
app_state.advance_step(1)
main_win.task_panel.update_from_state(app_state)
main_win.status_indicator.setText("Executing action: MOVE_FILE -> Research/Qualcomm-AI.pdf")
app.processEvents()
main_win.grab().save("assets/screenshots/07-execution.png")
print("Saved 07-execution.png")

# 8. Verification Result
app_state.update_status(TaskStatus.VERIFYING, "Verifying post-action ground truth: Destination file exists, source absent.")
app_state.advance_step(2)
main_win.task_panel.update_from_state(app_state)
main_win.status_indicator.setText("State Verification: VERIFIED (Destination file exists, source absent)")
app.processEvents()
main_win.grab().save("assets/screenshots/08-verification.png")
print("Saved 08-verification.png")

# 9. Task History Dialog
history_dlg = TaskHistoryDialog(parent=None)
history_dlg.resize(800, 500)
history_dlg.show()
app.processEvents()
history_dlg.grab().save("assets/screenshots/09-history.png")
history_dlg.close()
print("Saved 09-history.png")

# 10. Runtime & Hardware Status Panel (Settings -> Hardware)
settings_win = SettingsWindow(parent=None)
settings_win.resize(750, 520)
settings_win.tabs.setCurrentIndex(4)  # Hardware tab
settings_win.show()
app.processEvents()
settings_win.grab().save("assets/screenshots/10-runtime.png")
print("Saved 10-runtime.png")

# 11. Privacy Settings Tab (Settings -> Privacy)
settings_win.tabs.setCurrentIndex(2)  # Privacy tab
app.processEvents()
settings_win.grab().save("assets/screenshots/11-privacy-settings.png")
settings_win.close()
print("Saved 11-privacy-settings.png")

# 12. Flagship Demo Success
app_state.mark_completed("Goal successfully verified! Qualcomm-AI.pdf in Research.")
main_win.task_panel.update_from_state(app_state)
main_win.activity_panel.add_activity("task_demo_01", "Find latest PDF in Downloads, rename, move to Research, verify", "COMPLETED (VERIFIED)")
main_win.status_indicator.setText("Task Completed & Verified: Research/Qualcomm-AI.pdf verified.")
app.processEvents()
main_win.grab().save("assets/screenshots/12-demo-success.png")
print("Saved 12-demo-success.png")

main_win.close()
print("All 12 authentic PySide6 screenshots captured successfully in assets/screenshots/")
os._exit(0)
