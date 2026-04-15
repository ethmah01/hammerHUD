from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel,
                             QTextEdit, QHBoxLayout, QMessageBox, QApplication, 
                             QTabWidget, QComboBox, QSpinBox, QGroupBox, QLineEdit, QFileDialog)
from PyQt6.QtCore import Qt

class SettingsWindow(QWidget):
    def __init__(self, config_manager, tracker, reader_starter, overlay_manager, hand_logger):
        super().__init__()
        self.config = config_manager
        self.tracker = tracker
        self.reader_starter = reader_starter
        self.overlay_manager = overlay_manager
        self.hand_logger = hand_logger
        
        self.setWindowTitle("HammerHUD — Poker HUD Control Panel")
        self.resize(520, 480)
        
        self.setStyleSheet("""
            QWidget { background-color: #1a1a2e; color: #e0e0e0; font-family: 'Segoe UI'; font-size: 13px; }
            QPushButton { background-color: #16213e; border: 1px solid #0f3460; padding: 8px 14px; border-radius: 4px; color: #e0e0e0; }
            QPushButton:hover { background-color: #0f3460; }
            QTextEdit { background-color: #0d1117; border: 1px solid #30363d; color: #c9d1d9; padding: 6px; border-radius: 4px; }
            QTabWidget::pane { border: 1px solid #30363d; background-color: #1a1a2e; }
            QTabBar::tab { background: #16213e; padding: 8px 20px; margin: 2px; border-radius: 3px; color: #8b949e; }
            QTabBar::tab:selected { background: #0f3460; color: #e0e0e0; }
            QGroupBox { border: 1px solid #30363d; border-radius: 6px; margin-top: 10px; padding-top: 16px; font-weight: bold; color: #58a6ff; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            QComboBox, QSpinBox { background-color: #0d1117; border: 1px solid #30363d; padding: 4px 8px; border-radius: 3px; color: #c9d1d9; }
            QLabel#statusLabel { color: #58a6ff; font-size: 12px; }
            QLabel#errorLabel { color: #f85149; font-size: 12px; }
        """)
        
        main_layout = QVBoxLayout()
        self.tabs = QTabWidget()
        
        # --- TAB 1: HUD Controls ---
        self.hud_tab = QWidget()
        hud_layout = QVBoxLayout()
        
        # Status Group
        status_group = QGroupBox("Live Scanner Status")
        status_layout = QVBoxLayout()
        self.status_label = QLabel("Scanning for Ignition processes...")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        
        restart_btn = QPushButton("⟳ Restart Scanner")
        restart_btn.clicked.connect(self.restart_scanner)
        status_layout.addWidget(restart_btn)
        status_group.setLayout(status_layout)
        hud_layout.addWidget(status_group)
        
        # Hero Seat Config
        hero_group = QGroupBox("Hero Configuration")
        hero_layout = QHBoxLayout()
        hero_layout.addWidget(QLabel("Your Seat:"))
        self.hero_spin = QSpinBox()
        self.hero_spin.setRange(1, 9)
        hero_seat = self.config.get("hero_seat", 7)
        self.hero_spin.setValue(hero_seat)
        self.hero_spin.valueChanged.connect(self.change_hero_seat)
        hero_layout.addWidget(self.hero_spin)
        
        hero_layout.addWidget(QLabel("  Table Size:"))
        self.size_combo = QComboBox()
        self.size_combo.addItems(["6-Max", "9-Max"])
        if self.config.get("table_size", 6) == 9:
            self.size_combo.setCurrentText("9-Max")
        self.size_combo.currentTextChanged.connect(self.change_table_size)
        hero_layout.addWidget(self.size_combo)
        
        hero_group.setLayout(hero_layout)
        hud_layout.addWidget(hero_group)
        
        # Apply hero seat on startup
        self.tracker.set_hero_seat(hero_seat)
        
        # Session Controls
        ctrl_group = QGroupBox("Session Controls")
        ctrl_layout = QVBoxLayout()
        # Save Path configuration
        save_path_layout = QHBoxLayout()
        save_path_layout.addWidget(QLabel("Save Hand Histories to:"))
        self.save_path_input = QLineEdit()
        self.save_path_input.setText(self.config.get("hand_history_save_path", ""))
        save_path_layout.addWidget(self.save_path_input)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_save_path)
        save_path_layout.addWidget(browse_btn)
        ctrl_layout.addLayout(save_path_layout)
        
        # Clear Session
        clear_btn = QPushButton("🗑 Clear Session Stats")
        clear_btn.setStyleSheet("QPushButton { background-color: #3d1f1f; border-color: #6e3030; } QPushButton:hover { background-color: #5a2d2d; }")
        clear_btn.clicked.connect(self.clear_session)
        ctrl_layout.addWidget(clear_btn)
        
        ctrl_group.setLayout(ctrl_layout)
        hud_layout.addWidget(ctrl_group)
        
        # Manual Paste (fallback)
        paste_group = QGroupBox("Manual Paste (Fallback)")
        paste_layout = QVBoxLayout()
        self.paste_area = QTextEdit()
        self.paste_area.setMaximumHeight(100)
        self.paste_area.setPlaceholderText("Paste hand history text here for manual parsing...")
        paste_layout.addWidget(self.paste_area)
        
        parse_btn = QPushButton("Parse Pasted Hands")
        parse_btn.clicked.connect(self.parse_manual)
        paste_layout.addWidget(parse_btn)
        paste_group.setLayout(paste_layout)
        hud_layout.addWidget(paste_group)
        
        hud_layout.addStretch()
        self.hud_tab.setLayout(hud_layout)
        self.tabs.addTab(self.hud_tab, "HUD Controls")
        
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)
        
        # Initialize overlay with current state
        self.overlay_manager.update_session(self.tracker)
    
    def browse_save_path(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Hand History Save Directory")
        if directory:
            self.save_path_input.setText(directory)
            self.config.set("hand_history_save_path", directory)
            self.hand_logger.set_path(directory)
            QMessageBox.information(self, "Path Updated", f"Hands will now be saved to:\n{directory}")

    def update_reader_status(self, info: dict):
        """Called periodically to update the status display."""
        hands = info.get('hands_processed', 0)
        phase = info.get('phase', 'unknown')
        hand_id = info.get('hand_id', 'N/A')
        active = info.get('active_seats', [])
        
        if hands > 0:
            self.status_label.setText(
                f"✅ Connected | Hands: {hands} | Phase: {phase}\n"
                f"Hand #{hand_id} | Active seats: {active}"
            )
            self.status_label.setObjectName("statusLabel")
        elif active:
            self.status_label.setText(f"⏳ Waiting for first hand to complete...\nActive seats: {active}")
        else:
            pids = info.get('pids_found', 0)
            if pids > 0:
                self.status_label.setText(f"🔍 Found {pids} Ignition processes. Reading memory...")
            else:
                self.status_label.setText("❌ No Ignition processes found. Please open the game.")
                self.status_label.setObjectName("errorLabel")
    
    def restart_scanner(self):
        success = self.reader_starter()
        if success:
            self.status_label.setText("⟳ Scanner restarted. Scanning for Ignition...")
        else:
            self.status_label.setText("❌ Failed to restart scanner. Check terminal.")
            self.status_label.setObjectName("errorLabel")
    
    def change_hero_seat(self, seat):
        self.config.set("hero_seat", seat)
        self.tracker.set_hero_seat(seat)
        self.overlay_manager.update_session(self.tracker)
    
    def change_table_size(self, text):
        size = 9 if text == "9-Max" else 6
        self.overlay_manager.set_table_size(size, self.tracker)
    
    def parse_manual(self):
        text = self.paste_area.toPlainText()
        if text.strip():
            updated = self.tracker.process_hand_text(text)
            if updated:
                self.overlay_manager.update_session(self.tracker)
                QMessageBox.information(self, "Success", "Parsed hands! HUD updated.")
            else:
                QMessageBox.warning(self, "Parse Result", "No new valid hands found.")
            self.paste_area.clear()
    
    def clear_session(self):
        self.tracker.clear_session()
        self.overlay_manager.update_session(self.tracker)
        QMessageBox.information(self, "Cleared", "Session stats reset. Hero lifetime stats retained.")
    
    def closeEvent(self, event):
        QApplication.quit()
