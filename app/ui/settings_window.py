"""
VisionPilot Settings Window.

Provides configuration tabs for General, Voice, Automation, Privacy, AI Runtime,
and About. Phase 10: AI Runtime tab displays Snapdragon hardware telemetry,
provider availability, and on-demand benchmark results.
"""
from typing import Optional
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QCheckBox,
    QComboBox, QSpinBox, QFrame, QScrollArea, QMessageBox, QProgressBar
)
from app.core.config import config
from app.core.logger import logger
from app.core.state import app_state
from app.hardware.device_detector import device_detector
from app.hardware.runtime_detector import runtime_detector
from app.hardware.provider_selector import provider_selector
from app.hardware.benchmark_engine import benchmark_engine as bench_engine
from app.hardware.models import WorkloadType, ExecutionMode
from app.voice.audio_capture import AudioCapture
from app.voice.voice_service import voice_service
from app.perception.perception_engine import perception_engine
from app.perception.models import PerceptionRequest, CaptureScope
from app.services.history_service import history_service


class SettingsWindow(QDialog):
    """Configuration and telemetry dialog."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings — VisionPilot")
        self.resize(600, 480)
        self.setMinimumSize(540, 420)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Tab Widget
        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._create_general_tab(), "General")
        self.tabs.addTab(self._create_automation_tab(), "Automation")
        self.tabs.addTab(self._create_privacy_tab(), "Privacy")
        self.tabs.addTab(self._create_voice_tab(), "Voice")
        self.tabs.addTab(self._create_runtime_tab(), "AI Runtime")
        self.tabs.addTab(self._create_about_tab(), "About")

        layout.addWidget(self.tabs)

        # Footer Buttons
        footer = QHBoxLayout()
        footer.addStretch()
        close_btn = QPushButton("Close", self)
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

    def _create_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Theme
        theme_row = QHBoxLayout()
        theme_label = QLabel("Theme:", widget)
        theme_label.setStyleSheet("font-weight: 500;")
        self.theme_combo = QComboBox(widget)
        self.theme_combo.addItems(["Light (Default)", "System (Future)"])
        theme_row.addWidget(theme_label)
        theme_row.addStretch()
        theme_row.addWidget(self.theme_combo)

        # Log level
        log_row = QHBoxLayout()
        log_label = QLabel("Log Level:", widget)
        log_label.setStyleSheet("font-weight: 500;")
        log_val = QLabel(config.log_level, widget)
        log_val.setStyleSheet("color: #64748B; font-family: monospace;")
        log_row.addWidget(log_label)
        log_row.addStretch()
        log_row.addWidget(log_val)

        layout.addLayout(theme_row)
        layout.addLayout(log_row)
        layout.addStretch()
        return widget

    def _create_automation_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        info = QLabel("Configure computer-use automation and safety boundaries.", widget)
        info.setStyleSheet("color: #64748B; font-size: 12px;")
        layout.addWidget(info)

        self.chk_auto_low = QCheckBox("Automatically approve LOW-risk actions (e.g. read screen, open app)", widget)
        self.chk_auto_low.setChecked(config.safety.auto_approve_low_risk)

        self.chk_confirm_med = QCheckBox("Require confirmation for MEDIUM-risk actions (e.g. rename, move files)", widget)
        self.chk_confirm_med.setChecked(config.safety.confirm_medium_risk)

        self.chk_confirm_high = QCheckBox("Require confirmation for HIGH-risk actions (e.g. delete, send messages)", widget)
        self.chk_confirm_high.setChecked(config.safety.confirm_high_risk)
        self.chk_confirm_high.setEnabled(False)  # High risk confirmation cannot be disabled per Rule 5

        retries_row = QHBoxLayout()
        retries_lbl = QLabel("Max Recovery Retries:", widget)
        self.spin_retries = QSpinBox(widget)
        self.spin_retries.setRange(1, 5)
        self.spin_retries.setValue(config.safety.max_consecutive_retries)
        retries_row.addWidget(retries_lbl)
        retries_row.addStretch()
        retries_row.addWidget(self.spin_retries)

        layout.addWidget(self.chk_auto_low)
        layout.addWidget(self.chk_confirm_med)
        layout.addWidget(self.chk_confirm_high)
        layout.addLayout(retries_row)
        layout.addStretch()
        return widget

    def _create_privacy_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        title = QLabel("Privacy & Security Architecture", widget)
        title.setStyleSheet("font-weight: 600; font-size: 13px; color: #0F172A;")
        layout.addWidget(title)

        c1 = QLabel("✓ Local-First: Screen analysis and task planning operate entirely on your PC.", widget)
        c1.setStyleSheet("color: #059669; font-size: 12px;")
        c2 = QLabel("✓ No Background Surveillance: Screen capture occurs only on active user tasks.", widget)
        c2.setStyleSheet("color: #059669; font-size: 12px;")
        c3 = QLabel("✓ Credential Protection: Passwords and tokens are strictly shielded from AI models.", widget)
        c3.setStyleSheet("color: #059669; font-size: 12px;")

        layout.addWidget(c1)
        layout.addWidget(c2)
        layout.addWidget(c3)

        # Task History Retention Section
        ret_title = QLabel("Task History & Audit Trail", widget)
        ret_title.setStyleSheet("font-weight: 600; font-size: 13px; color: #0F172A; margin-top: 10px;")
        layout.addWidget(ret_title)

        ret_row = QHBoxLayout()
        ret_lbl = QLabel("History Retention:", widget)
        ret_lbl.setStyleSheet("font-size: 12px; color: #334155;")
        self.retention_combo = QComboBox(widget)
        self.retention_combo.addItems(["30 Days (Default)", "7 Days", "90 Days", "Forever"])
        if config.history.retention_days == 7:
            self.retention_combo.setCurrentIndex(1)
        elif config.history.retention_days == 90:
            self.retention_combo.setCurrentIndex(2)
        elif config.history.retention_days == 0:
            self.retention_combo.setCurrentIndex(3)
        else:
            self.retention_combo.setCurrentIndex(0)

        ret_row.addWidget(ret_lbl)
        ret_row.addStretch()
        ret_row.addWidget(self.retention_combo)
        layout.addLayout(ret_row)

        clear_row = QHBoxLayout()
        clear_lbl = QLabel("Wipe local task records, verifications, and audit trails:", widget)
        clear_lbl.setStyleSheet("font-size: 11px; color: #64748B;")
        clear_btn = QPushButton("Clear Task History", widget)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #FEF2F2;
                color: #DC2626;
                border: 1px solid #FECACA;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #FEE2E2;
            }
        """)
        clear_btn.clicked.connect(self._handle_clear_history)

        clear_row.addWidget(clear_lbl, 1)
        clear_row.addWidget(clear_btn)
        layout.addLayout(clear_row)

        layout.addStretch()
        return widget

    def _handle_clear_history(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear Task History",
            "Are you sure you want to permanently clear your local task history?\n\n"
            "This will delete all saved task commands, plans, action records, "
            "verification results, and audit trails.\n\n"
            "Your application settings and personal files will NOT be affected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            history_service.clear_history()
            QMessageBox.information(self, "History Cleared", "Local task history has been safely cleared.")

    def _create_voice_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel("Voice Recognition Subsystem", widget)
        header.setStyleSheet("font-weight: 600; font-size: 13px; color: #0F172A;")
        layout.addWidget(header)

        # Microphones
        mic_row = QHBoxLayout()
        mic_lbl = QLabel("Input Device:", widget)
        mic_lbl.setStyleSheet("font-weight: 500; font-size: 12px;")
        self.mic_combo = QComboBox(widget)
        
        mics = AudioCapture.get_available_microphones()
        default_mic = AudioCapture.get_default_microphone_name()
        if mics:
            for mic in mics:
                self.mic_combo.addItem(mic)
            idx = self.mic_combo.findText(default_mic)
            if idx >= 0:
                self.mic_combo.setCurrentIndex(idx)
        else:
            self.mic_combo.addItem("No microphone detected")
            self.mic_combo.setEnabled(False)

        mic_row.addWidget(mic_lbl)
        mic_row.addStretch()
        mic_row.addWidget(self.mic_combo)
        layout.addLayout(mic_row)

        # Telemetry helper
        meta = voice_service.provider.metadata
        def _row(k: str, v: str) -> QHBoxLayout:
            r = QHBoxLayout()
            l1 = QLabel(f"{k}:", widget)
            l1.setStyleSheet("font-weight: 500; font-size: 12px;")
            l2 = QLabel(v, widget)
            l2.setStyleSheet("font-family: monospace; font-size: 12px; color: #0F172A;")
            r.addWidget(l1)
            r.addStretch()
            r.addWidget(l2)
            return r

        layout.addLayout(_row("Speech Provider", meta.provider_name))
        layout.addLayout(_row("Speech Model", meta.model_name))
        layout.addLayout(_row("Inference Accelerator", meta.accelerator))
        layout.addLayout(_row("Primary Language", meta.supported_languages[0] if meta.supported_languages else "en-US"))
        layout.addLayout(_row("Audio Backend", "PySide6 QtMultimedia (WASAPI)"))
        layout.addLayout(_row("Activation Mode", "Click-to-Record Toggle"))
        layout.addLayout(_row("Max Recording Limit", f"{config.voice.max_duration_seconds}s timeout"))

        # Privacy callouts
        privacy_note = QLabel(
            "Privacy Architecture:\n"
            "• 100% Local: Spoken audio is transcribed on-device; never transmitted to any cloud API.\n"
            "• Ephemeral Buffers: Audio is discarded immediately after transcription; raw recordings are never saved to disk.",
            widget
        )
        privacy_note.setStyleSheet("color: #059669; font-size: 11px; margin-top: 6px; line-height: 1.4;")
        privacy_note.setWordWrap(True)
        layout.addWidget(privacy_note)

        layout.addStretch()
        return widget

    def _create_runtime_tab(self) -> QWidget:
        """Phase 10: Hardware telemetry, provider status, and on-demand benchmark panel."""
        # Scrollable container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        def _header(text: str) -> QLabel:
            lbl = QLabel(text, widget)
            lbl.setStyleSheet(
                "font-weight: 600; font-size: 13px; color: #0F172A; "
                "margin-top: 8px; padding-bottom: 2px; "
                "border-bottom: 1px solid #E2E8F0;"
            )
            return lbl

        def _row(k: str, v: str) -> QHBoxLayout:
            r = QHBoxLayout()
            l1 = QLabel(f"{k}:", widget)
            l1.setStyleSheet("font-weight: 500; font-size: 11px; color: #334155;")
            l2 = QLabel(v, widget)
            l2.setStyleSheet("font-family: monospace; font-size: 11px; color: #0F172A;")
            r.addWidget(l1)
            r.addStretch()
            r.addWidget(l2)
            return r

        # ── Hardware ──────────────────────────────────────────────────────────
        layout.addWidget(_header("Snapdragon Hardware Audit"))
        hw_report = runtime_detector.audit_hardware()

        layout.addLayout(_row("CPU", hw_report.cpu_name))
        layout.addLayout(_row("GPU", hw_report.gpu_name))
        layout.addLayout(_row(
            "NPU",
            f"{hw_report.npu_name} (Detected)" if hw_report.npu_present else "Not detected"
        ))
        layout.addLayout(_row("RAM", f"{hw_report.ram_total_gb:.1f} GB total, {hw_report.ram_available_gb:.1f} GB free"))
        layout.addLayout(_row("Platform", hw_report.platform_summary))

        # ── Provider Availability ────────────────────────────────────────────
        layout.addWidget(_header("Runtime Provider Availability"))

        try:
            providers = runtime_detector.enumerate_providers()
        except Exception:
            providers = []

        if providers:
            prov_items = providers.values() if isinstance(providers, dict) else providers
            for p in prov_items:
                row = QHBoxLayout()
                p_name = QLabel(p.display_name, widget)
                p_name.setStyleSheet("font-size: 11px; color: #0F172A;")
                p_status_text = "✓ Available" if p.available else f"✗ {p.failure_reason or 'Unavailable'}"
                p_status = QLabel(p_status_text, widget)
                color = "#16A34A" if p.available else "#DC2626"
                p_status.setStyleSheet(f"font-size: 11px; color: {color}; font-family: monospace;")
                row.addWidget(p_name)
                row.addStretch()
                row.addWidget(p_status)
                layout.addLayout(row)
        else:
            layout.addWidget(QLabel("Provider enumeration not available.", widget))

        # ── Execution Mode ───────────────────────────────────────────────────
        layout.addWidget(_header("AI Execution Mode"))

        mode_row = QHBoxLayout()
        mode_lbl = QLabel("Current Mode:", widget)
        mode_lbl.setStyleSheet("font-weight: 500; font-size: 11px; color: #334155;")
        current_mode = provider_selector.get_execution_mode()
        mode_val = QLabel(current_mode.value, widget)
        mode_val.setStyleSheet("font-family: monospace; font-size: 11px; color: #1E40AF; font-weight: 600;")
        mode_row.addWidget(mode_lbl)
        mode_row.addStretch()
        mode_row.addWidget(mode_val)
        layout.addLayout(mode_row)

        mode_combo = QComboBox(widget)
        for m in ExecutionMode:
            mode_combo.addItem(m.value)
        mode_combo.setCurrentText(current_mode.value)
        mode_combo.setStyleSheet("font-size: 11px;")

        def _set_mode(idx):
            chosen = ExecutionMode(mode_combo.currentText())
            provider_selector.set_execution_mode(chosen)
            mode_val.setText(chosen.value)
            logger.info(f"[SettingsWindow] AI execution mode changed to: {chosen.value}")

        mode_combo.currentIndexChanged.connect(_set_mode)
        layout.addWidget(mode_combo)

        # ── Perception ───────────────────────────────────────────────────────
        layout.addWidget(_header("Screen Perception Subsystem"))
        layout.addLayout(_row("UI Automation", "Windows UI Automation Core (Native)"))
        layout.addLayout(_row("OCR Engine", "Windows Media OCR (WinRT Native)"))
        layout.addLayout(_row("OCR Accelerator", "CPU (On-Device, x64 Emulation)"))
        layout.addLayout(_row("Visual Grounding", "Spatial & Semantic Fusion (Deterministic)"))

        diag_layout = QHBoxLayout()
        scan_btn = QPushButton("Run Perception Diagnostic", widget)
        scan_btn.setStyleSheet("font-size: 11px; padding: 4px 10px;")
        diag_lbl = QLabel("Ready", widget)
        diag_lbl.setStyleSheet("color: #64748B; font-size: 10px; font-family: monospace;")

        def _run_diag():
            diag_lbl.setText("Scanning...")
            try:
                state = perception_engine.perceive(PerceptionRequest(scope=CaptureScope.ACTIVE_WINDOW))
                win = state.active_window.title[:20] if state.active_window else "Desktop"
                diag_lbl.setText(
                    f"{state.metadata.get('duration_ms', 0)}ms | '{win}' | "
                    f"{len(state.fused_elements)} el | {len(state.ocr_regions)} OCR"
                )
            except Exception as ex:
                diag_lbl.setText(f"Error: {ex}")

        scan_btn.clicked.connect(_run_diag)
        diag_layout.addWidget(scan_btn)
        diag_layout.addWidget(diag_lbl)
        diag_layout.addStretch()
        layout.addLayout(diag_layout)

        # ── Benchmark ────────────────────────────────────────────────────────
        layout.addWidget(_header("On-Device Performance Benchmark"))

        bench_note = QLabel(
            "Benchmarks measure real on-device performance. Results reflect Oryon CPU "
            "with Windows Prism x64 emulation. No numbers are fabricated.",
            widget
        )
        bench_note.setStyleSheet("color: #64748B; font-size: 10px;")
        bench_note.setWordWrap(True)
        layout.addWidget(bench_note)

        # Workload selector
        workload_row = QHBoxLayout()
        wl_lbl = QLabel("Workload:", widget)
        wl_lbl.setStyleSheet("font-weight: 500; font-size: 11px; color: #334155;")
        self._bench_combo = QComboBox(widget)
        self._bench_combo.setStyleSheet("font-size: 11px;")
        for wl in WorkloadType:
            self._bench_combo.addItem(wl.value, wl)
        workload_row.addWidget(wl_lbl)
        workload_row.addWidget(self._bench_combo)
        workload_row.addStretch()
        layout.addLayout(workload_row)

        # Run button + progress bar
        bench_row = QHBoxLayout()
        self._bench_run_btn = QPushButton("▶  Run Benchmark", widget)
        self._bench_run_btn.setStyleSheet(
            "font-size: 11px; font-weight: 600; padding: 5px 14px; "
            "background: #1E40AF; color: white; border-radius: 4px;"
        )
        bench_row.addWidget(self._bench_run_btn)
        bench_row.addStretch()
        layout.addLayout(bench_row)

        self._bench_progress = QProgressBar(widget)
        self._bench_progress.setRange(0, 0)  # indeterminate
        self._bench_progress.setVisible(False)
        self._bench_progress.setFixedHeight(6)
        layout.addWidget(self._bench_progress)

        # Result labels
        self._bench_result_lbl = QLabel("", widget)
        self._bench_result_lbl.setStyleSheet(
            "font-family: monospace; font-size: 10px; color: #0F172A; "
            "background: #F8FAFC; border: 1px solid #E2E8F0; "
            "padding: 6px; border-radius: 3px;"
        )
        self._bench_result_lbl.setWordWrap(True)
        self._bench_result_lbl.setVisible(False)
        layout.addWidget(self._bench_result_lbl)

        def _run_benchmark():
            wl: WorkloadType = self._bench_combo.currentData()
            self._bench_run_btn.setEnabled(False)
            self._bench_progress.setVisible(True)
            self._bench_result_lbl.setVisible(False)

            class _BenchWorker(QThread):
                done = Signal(object)

                def __init__(self, workload):
                    super().__init__()
                    self._wl = workload

                def run(self):
                    try:
                        result = bench_engine.run_benchmark(self._wl, iterations=5, warmup=1)
                        self.done.emit(result)
                    except Exception as e:
                        self.done.emit(e)

            self._bench_worker = _BenchWorker(wl)

            def _on_done(result):
                self._bench_progress.setVisible(False)
                self._bench_run_btn.setEnabled(True)
                if isinstance(result, Exception):
                    self._bench_result_lbl.setText(f"Benchmark failed: {result}")
                    self._bench_result_lbl.setStyleSheet(
                        "font-family: monospace; font-size: 10px; color: #DC2626; "
                        "background: #FEF2F2; border: 1px solid #FECACA; "
                        "padding: 6px; border-radius: 3px;"
                    )
                else:
                    if result.success:
                        text = (
                            f"Workload:  {result.workload.value}\n"
                            f"Provider:  {result.provider}\n"
                            f"Runtime:   {result.runtime}\n"
                            f"Device:    {result.device}\n"
                            f"First:     {result.first_latency_ms:.2f} ms\n"
                            f"Average:   {result.average_latency_ms:.2f} ms\n"
                            f"P50:       {result.p50_latency_ms:.2f} ms\n"
                            f"P95:       {result.p95_latency_ms:.2f} ms\n"
                            f"Rate:      {result.throughput:.1f} ops/sec\n"
                            f"Memory:    {result.memory_before_mb:.1f} → {result.memory_after_mb:.1f} MB\n"
                            f"Authentic: 100% measured on-device."
                        )
                        self._bench_result_lbl.setStyleSheet(
                            "font-family: monospace; font-size: 10px; color: #0F172A; "
                            "background: #F0FDF4; border: 1px solid #BBF7D0; "
                            "padding: 6px; border-radius: 3px;"
                        )
                    else:
                        text = f"Benchmark skipped — {result.error}"
                        self._bench_result_lbl.setStyleSheet(
                            "font-family: monospace; font-size: 10px; color: #92400E; "
                            "background: #FFFBEB; border: 1px solid #FDE68A; "
                            "padding: 6px; border-radius: 3px;"
                        )
                    self._bench_result_lbl.setText(text)
                self._bench_result_lbl.setVisible(True)

            self._bench_worker.done.connect(_on_done)
            self._bench_worker.start()

        self._bench_run_btn.clicked.connect(_run_benchmark)

        # Truthfulness note
        truth_note = QLabel(
            "Truthfulness: Hardware acceleration is only reported when verified by the "
            "runtime detection layer. CPU execution is never relabeled as NPU/GPU.",
            widget
        )
        truth_note.setStyleSheet("color: #64748B; font-size: 10px; margin-top: 4px;")
        truth_note.setWordWrap(True)
        layout.addWidget(truth_note)

        layout.addStretch()
        scroll.setWidget(widget)
        return scroll

    def _create_about_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        name = QLabel(f"{config.app_name} v{config.version}", widget)
        name.setStyleSheet("font-weight: bold; font-size: 18px; color: #1E40AF;")

        tagline = QLabel(config.tagline, widget)
        tagline.setStyleSheet("font-weight: 500; font-size: 13px; color: #64748B;")

        desc = QLabel(
            "Privacy-first visual computer-use AI agent designed for Snapdragon AI PCs.\n"
            "Automates desktop tasks through vision, UI automation, and strict safety controls.",
            widget
        )
        desc.setStyleSheet("font-size: 12px; color: #334155; line-height: 1.4;")
        desc.setWordWrap(True)

        layout.addWidget(name)
        layout.addWidget(tagline)
        layout.addWidget(desc)
        layout.addStretch()
        return widget
