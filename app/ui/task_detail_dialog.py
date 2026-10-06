"""
VisionPilot Task Detail Dialog.

Presents a comprehensive, privacy-redacted audit view for an individual task:
- User command and source
- Execution timeline and duration
- Formulated plan metadata
- Step-by-step action outcomes
- Postcondition verification evidence
- Recovery decisions and attempts
- Append-only chronological audit trail
"""
from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame,
    QTabWidget, QTextEdit, QSizePolicy
)
from app.services.history_service import history_service


class TaskDetailDialog(QDialog):
    """Structured inspection dialog for a completed or historical task."""

    def __init__(self, task_id: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.task_id = task_id
        self.setWindowTitle(f"Task Audit Details — {task_id}")
        self.resize(650, 550)
        self.setMinimumSize(550, 450)
        self._init_ui()

    def _init_ui(self) -> None:
        data = history_service.get_task_details(self.task_id)
        if not data or not data.get("task"):
            layout = QVBoxLayout(self)
            lbl = QLabel(f"Task record [{self.task_id}] not found.", self)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)
            return

        task = data["task"]
        plan = data.get("plan")
        actions = data.get("actions", [])
        verifications = data.get("verifications", [])
        recoveries = data.get("recoveries", [])
        audit_events = data.get("audit_events", [])

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # Header Card
        header_card = QFrame(self)
        header_card.setProperty("class", "card")
        header_card.setStyleSheet("background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px;")
        h_layout = QVBoxLayout(header_card)
        h_layout.setSpacing(6)

        # Title & Badges
        top_row = QHBoxLayout()
        cmd_text = task.get("user_command", "")
        title_lbl = QLabel(cmd_text, header_card)
        title_lbl.setStyleSheet("font-weight: 700; font-size: 15px; color: #0F172A;")
        title_lbl.setWordWrap(True)

        source_badge = QLabel(task.get("command_source", "TEXT").upper(), header_card)
        source_badge.setStyleSheet("background: #F1F5F9; color: #475569; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 4px;")

        status_str = task.get("status", "COMPLETED").upper()
        status_badge = QLabel(status_str, header_card)
        if status_str in ("COMPLETED", "VERIFIED_SUCCESS"):
            status_badge.setStyleSheet("background: #ECFDF5; color: #059669; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 4px;")
        elif status_str in ("FAILED", "BLOCKED"):
            status_badge.setStyleSheet("background: #FEF2F2; color: #DC2626; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 4px;")
        elif status_str in ("UNCERTAIN", "PARTIALLY_COMPLETED"):
            status_badge.setStyleSheet("background: #FFFBEB; color: #D97706; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 4px;")
        else:
            status_badge.setStyleSheet("background: #F0F9FF; color: #0284C7; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 4px;")

        top_row.addWidget(title_lbl, 1)
        top_row.addWidget(source_badge)
        top_row.addWidget(status_badge)
        h_layout.addLayout(top_row)

        # Meta row
        dur_sec = (task.get("duration_ms", 0.0) or 0.0) / 1000.0
        dur_text = f"{dur_sec:.2f}s" if dur_sec > 0 else "< 0.1s"
        created_str = task.get("created_at", "")
        time_part = created_str.split("T")[1][:8] if "T" in created_str else created_str
        verif_status = task.get("verification_status") or "NOT_VERIFIED"

        meta_lbl = QLabel(
            f"Created: {time_part}  •  Duration: {dur_text}  •  Verification: {verif_status}",
            header_card
        )
        meta_lbl.setStyleSheet("font-size: 12px; color: #64748B;")
        h_layout.addWidget(meta_lbl)

        main_layout.addWidget(header_card)

        # Tabbed Detail View
        tabs = QTabWidget(self)

        # 1. Summary & Actions Tab
        tabs.addTab(self._build_actions_tab(plan, actions, verifications, recoveries), "Actions & Verification")

        # 2. Audit Trail Tab
        tabs.addTab(self._build_audit_tab(audit_events), "Audit Trail")

        main_layout.addWidget(tabs, 1)

        # Close button
        footer = QHBoxLayout()
        footer.addStretch()
        close_btn = QPushButton("Close", self)
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        main_layout.addLayout(footer)

    def _build_actions_tab(
        self,
        plan: Optional[Dict[str, Any]],
        actions: list,
        verifications: list,
        recoveries: list
    ) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea(widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        c_layout = QVBoxLayout(content)
        c_layout.setSpacing(10)

        # Plan summary
        if plan:
            plan_box = QFrame(content)
            plan_box.setStyleSheet("background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 10px;")
            p_layout = QVBoxLayout(plan_box)
            p_layout.setSpacing(4)
            p_title = QLabel(f"Plan [{plan.get('plan_id', '')}]: {plan.get('goal', '')}", plan_box)
            p_title.setStyleSheet("font-weight: 600; font-size: 12px; color: #1E293B;")
            p_meta = QLabel(
                f"Model: {plan.get('model', '')} ({plan.get('provider', '')})  •  Steps: {plan.get('number_of_steps', 0)}  •  Risk: {plan.get('risk_summary', 'SAFE')}",
                plan_box
            )
            p_meta.setStyleSheet("font-size: 11px; color: #64748B;")
            p_layout.addWidget(p_title)
            p_layout.addWidget(p_meta)
            c_layout.addWidget(plan_box)

        # Actions List
        act_title = QLabel("Executed Actions:", content)
        act_title.setStyleSheet("font-weight: 600; font-size: 13px; color: #0F172A; margin-top: 6px;")
        c_layout.addWidget(act_title)

        if not actions:
            no_act = QLabel("No actions were executed for this task.", content)
            no_act.setStyleSheet("font-size: 12px; color: #94A3B8;")
            c_layout.addWidget(no_act)
        else:
            for idx, a in enumerate(actions):
                row = QFrame(content)
                row.setStyleSheet("background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px; padding: 8px;")
                r_layout = QVBoxLayout(row)
                r_layout.setSpacing(4)

                header = QHBoxLayout()
                success = a.get("result_status") == "SUCCESS"
                icon = "✓" if success else "✕"
                icon_color = "#059669" if success else "#DC2626"
                step_lbl = QLabel(f"{icon} Step {idx + 1}: {a.get('capability', '')}", row)
                step_lbl.setStyleSheet(f"font-weight: 600; font-size: 12px; color: {icon_color};")

                dur = a.get("duration_ms", 0.0)
                dur_lbl = QLabel(f"{dur:.1f}ms", row)
                dur_lbl.setStyleSheet("font-size: 11px; color: #64748B;")

                header.addWidget(step_lbl, 1)
                header.addWidget(dur_lbl)
                r_layout.addLayout(header)

                target = a.get("target_reference", "")
                if target:
                    target_lbl = QLabel(f"Target: {target}", row)
                    target_lbl.setStyleSheet("font-size: 11px; color: #475569;")
                    r_layout.addWidget(target_lbl)

                if a.get("error_message_redacted"):
                    err_lbl = QLabel(f"Error: {a.get('error_message_redacted')}", row)
                    err_lbl.setStyleSheet("font-size: 11px; color: #DC2626;")
                    err_lbl.setWordWrap(True)
                    r_layout.addWidget(err_lbl)

                c_layout.addWidget(row)

        # Verifications
        if verifications:
            verif_title = QLabel("Verification Results:", content)
            verif_title.setStyleSheet("font-weight: 600; font-size: 13px; color: #0F172A; margin-top: 6px;")
            c_layout.addWidget(verif_title)

            for v in verifications:
                v_box = QFrame(content)
                v_box.setStyleSheet("background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px;")
                v_layout = QVBoxLayout(v_box)
                v_layout.setSpacing(3)

                v_ok = v.get("verified", False)
                v_icon = "✓" if v_ok else "⚠"
                v_color = "#059669" if v_ok else "#D97706"

                v_hdr = QLabel(f"{v_icon} Strategy: {v.get('strategy', '')}  (Status: {v.get('status', '')})", v_box)
                v_hdr.setStyleSheet(f"font-weight: 600; font-size: 12px; color: {v_color};")
                v_layout.addWidget(v_hdr)

                if v.get("expected_state_summary"):
                    v_exp = QLabel(f"Expected: {v.get('expected_state_summary')}", v_box)
                    v_exp.setStyleSheet("font-size: 11px; color: #475569;")
                    v_layout.addWidget(v_exp)

                if v.get("actual_state_summary"):
                    v_act = QLabel(f"Observed: {v.get('actual_state_summary')}", v_box)
                    v_act.setStyleSheet("font-size: 11px; color: #475569;")
                    v_layout.addWidget(v_act)

                c_layout.addWidget(v_box)

        # Recoveries
        if recoveries:
            rec_title = QLabel("Recovery Attempts:", content)
            rec_title.setStyleSheet("font-weight: 600; font-size: 13px; color: #0F172A; margin-top: 6px;")
            c_layout.addWidget(rec_title)

            for r in recoveries:
                r_box = QFrame(content)
                r_box.setStyleSheet("background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 6px; padding: 8px;")
                r_layout = QVBoxLayout(r_box)
                r_layout.setSpacing(3)
                r_hdr = QLabel(f"Attempt #{r.get('recovery_depth', 1)}: {r.get('decision', '')} ({r.get('outcome', 'UNKNOWN')})", r_box)
                r_hdr.setStyleSheet("font-weight: 600; font-size: 12px; color: #B45309;")
                r_reason = QLabel(f"Reason: {r.get('reason', '')}", r_box)
                r_reason.setStyleSheet("font-size: 11px; color: #78350F;")
                r_layout.addWidget(r_hdr)
                r_layout.addWidget(r_reason)
                c_layout.addWidget(r_box)

        c_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        return widget

    def _build_audit_tab(self, audit_events: list) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea(widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        c_layout = QVBoxLayout(content)
        c_layout.setSpacing(6)

        if not audit_events:
            empty_lbl = QLabel("No audit events recorded for this task.", content)
            empty_lbl.setStyleSheet("font-size: 12px; color: #94A3B8;")
            c_layout.addWidget(empty_lbl)
        else:
            for ev in audit_events:
                item = QFrame(content)
                item.setStyleSheet("background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 4px; padding: 6px 10px;")
                i_layout = QHBoxLayout(item)
                i_layout.setContentsMargins(0, 0, 0, 0)
                i_layout.setSpacing(8)

                ts = ev.get("timestamp", "")
                t_part = ts.split("T")[1][:8] if "T" in ts else ts
                time_lbl = QLabel(t_part, item)
                time_lbl.setStyleSheet("font-size: 11px; color: #94A3B8; font-weight: 500;")

                ev_type = ev.get("event_type", "EVENT")
                type_lbl = QLabel(ev_type, item)
                type_lbl.setStyleSheet("font-size: 11px; color: #0284C7; font-weight: 600; min-width: 130px;")

                msg = ev.get("message_redacted", "")
                msg_lbl = QLabel(msg, item)
                msg_lbl.setStyleSheet("font-size: 11px; color: #334155;")
                msg_lbl.setWordWrap(True)

                i_layout.addWidget(time_lbl)
                i_layout.addWidget(type_lbl)
                i_layout.addWidget(msg_lbl, 1)
                c_layout.addWidget(item)

        c_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        return widget
