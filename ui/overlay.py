import sys
from PyQt6.QtWidgets import QWidget, QFrame, QLabel, QVBoxLayout, QPushButton
from PyQt6.QtCore import Qt

class StatBadge(QWidget):
    def __init__(self, seat_id, config_manager, reset_callback=None, title="Player"):
        super().__init__()
        self.seat_id = str(seat_id)
        self.config = config_manager
        self.reset_callback = reset_callback
        self.title = title
        
        # Transparent top-level window
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._old_pos = None

        # Build inner frame that can actually be styled
        self.inner_frame = QFrame(self)
        self.inner_frame.setObjectName("SolidFrame")
        
        # We bump opacity slightly to 120 so Windows reliably catches the click!
        self.inner_frame.setStyleSheet("""
            QFrame#SolidFrame {
                background-color: rgba(20, 20, 20, 120);
                border-radius: 6px;
            }
            QLabel {
                color: #eaeaea;
                font-family: 'Segoe UI', Arial, sans-serif;
                background-color: transparent;
            }
            QPushButton#ResetBtn {
                background-color: rgba(60, 0, 0, 180);
                color: #ffcccc;
                font-size: 10px;
                border: 1px solid #440000;
                border-radius: 3px;
                padding: 1px 4px;
                font-weight: bold;
            }
            QPushButton#ResetBtn:hover {
                background-color: rgba(120, 0, 0, 220);
            }
        """)

        # Build UI inside the inner frame
        inner_layout = QVBoxLayout(self.inner_frame)
        inner_layout.setContentsMargins(5, 5, 5, 5)

        self.title_label = QLabel(f"<b style='color:#cdcdcd;'>{self.title}</b>")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.stats_label = QLabel("VPIP: --% | PFR: --%<br>Hands: 0")
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        # Hidden Reset Button (shows on hover)
        self.reset_btn = QPushButton("Reset Stats", self.inner_frame)
        self.reset_btn.setObjectName("ResetBtn")
        self.reset_btn.setFixedWidth(70)
        self.reset_btn.setVisible(False)
        self.reset_btn.clicked.connect(self.on_reset_clicked)
        
        inner_layout.addWidget(self.title_label)
        inner_layout.addWidget(self.stats_label)
        inner_layout.addWidget(self.reset_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Add the inner frame to the main widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.inner_frame)

        # Restore Position
        pos_data = self.config.get("badge_positions", {}).get(self.seat_id, {"x": 0, "y": 0})
        self.move(pos_data["x"], pos_data["y"])

    def update_stats(self, vpip, pfr, hands, hero_lifetime=False, player_name=None):
        if player_name:
            self.title_label.setText(f"<b style='color:#cdcdcd;'>{player_name}</b>")
        if hero_lifetime:
            self.stats_label.setText(f"<span style='color:#a8ff9b'>VPIP: {vpip:.0f}% | PFR: {pfr:.0f}%</span><br>Hands: {hands}")
        else:
            self.stats_label.setText(f"VPIP: {vpip:.0f}% | PFR: {pfr:.0f}%<br>Hands: {hands}")

    def on_reset_clicked(self):
        if self.reset_callback:
            self.reset_callback(self.seat_id)

    def enterEvent(self, event):
        """Show reset button on hover."""
        if self.seat_id != "hero":
            self.reset_btn.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hide reset button when mouse leaves."""
        self.reset_btn.setVisible(False)
        super().leaveEvent(event)

    # Make Draggable
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self, '_drag_pos'):
                del self._drag_pos
            # Save new position
            positions = self.config.get("badge_positions", {})
            positions[self.seat_id] = {"x": self.x(), "y": self.y()}
            self.config.set("badge_positions", positions)
            event.accept()

class OverlayManager:
    def __init__(self, config_manager, tracker):
        self.config = config_manager
        self.tracker = tracker
        self.badges: dict = {}
        self.table_size = self.config.get("table_size", 6)
        
        self.build_badges()
        
    def build_badges(self):
        for b in list(self.badges.values()):
            b.close()
        self.badges.clear()
        
        for i in range(1, self.table_size + 1):
            b = StatBadge(i, self.config, reset_callback=self.on_player_reset, title=f"Seat {i}")
            self.badges[i] = b
            b.show()
            
        # Hero badge
        hb = StatBadge("hero", self.config, title="Hero (Lifetime)")
        self.badges["hero"] = hb
        hb.show()

    def on_player_reset(self, seat_id):
        """Callback from StatBadge to reset a specific seat."""
        try:
            seat_num = int(seat_id)
            self.tracker.reset_seat(seat_num)
            self.update_session(self.tracker)
        except (ValueError, TypeError):
            pass
        
    def set_table_size(self, size: int, tracker):
        if self.table_size != size:
            self.table_size = size
            self.config.set("table_size", size)
            self.build_badges()
            self.update_session(tracker)

    def update_session(self, tracker, active_seats=None):
        # Determine which seats should be visible
        # Only hide players if we have a confirmed list of who is active.
        # This prevents flickering at the start of a hand.
        active_set = active_seats if active_seats else getattr(tracker, 'seated_seats', set())
        
        for i in range(1, self.table_size + 1):
            if i not in self.badges:
                continue
                
            is_hero = hasattr(tracker, 'hero_seat') and i == tracker.hero_seat
            # Only hide if it's the hero, or if we have a non-empty active set and the seat is missing
            should_hide = is_hero or (active_set and i not in active_set)
            
            if should_hide:
                self.badges[i].hide()
            else:
                self.badges[i].show()
                
            player = tracker.session_stats.get_seat(i)
            player_name = tracker.seat_players.get(i, f"Seat {i}")
            if player.hands_played >= 0:
                self.badges[i].update_stats(player.vpip_percent, player.pfr_percent, player.hands_played, player_name=player_name)
                
        # Hero stats
        if tracker.hero_stats and tracker.hero_stats.hands_played >= 0:
            hero_name = "Hero"
            if hasattr(tracker, 'hero_seat') and tracker.hero_seat in tracker.seat_players:
               hero_name = tracker.seat_players[tracker.hero_seat]
            self.badges["hero"].update_stats(tracker.hero_stats.vpip_percent, tracker.hero_stats.pfr_percent, tracker.hero_stats.hands_played, hero_lifetime=True, player_name=f"{hero_name} (Lifetime)")
            
    def shutdown(self):
        for b in self.badges.values():
            b.close()
