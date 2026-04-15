import sys
import logging
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
        """Creates or updates player badges based on current table size."""
        target_seats = {str(i) for i in range(1, self.table_size + 1)}
        target_seats.add("hero") # Always keep the lifetime hero badge
        
        current_seats = set(self.badges.keys())
        
        # 1. Remove badges that are no longer part of the table layout
        for seat_id in (current_seats - target_seats):
            logging.debug(f"Overlay: Removing badge for seat {seat_id}")
            if seat_id in self.badges:
                self.badges[seat_id].close()
                del self.badges[seat_id]
            
        # 2. Add badges for new seats in the layout
        for seat_id in (target_seats - current_seats):
            logging.debug(f"Overlay: Adding badge for seat {seat_id}")
            if seat_id == "hero":
                b = StatBadge("hero", self.config, title="Hero (Lifetime)")
            else:
                b = StatBadge(seat_id, self.config, reset_callback=self.on_player_reset, title=f"Seat {seat_id}")
            self.badges[seat_id] = b
            b.show()

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
        # active_seats is the set of 'confirmed_seated' from the memory reader
        # we convert to strings for safe comparison with badge keys
        active_set = {str(s) for s in active_seats} if active_seats is not None else None
        
        # Determine current hero seat (as string for ID matching)
        current_hero_id = str(tracker.hero_seat) if tracker.hero_seat is not None else None
        
        for seat_id, badge in self.badges.items():
            if seat_id == "hero":
                continue
                
            is_hero_seat = (current_hero_id is not None and seat_id == current_hero_id)
            
            # Badge is only shown if it's NOT the hero's current seat AND it's in the confirmed active set
            should_show = False
            if is_hero_seat:
                should_show = False # Hide the hero's on-table badge once detected
            elif active_set is None:
                # If no set provided at all, default to showing (initial state)
                should_show = True
            elif seat_id in active_set:
                # If set is provided and seat is in it, show it
                should_show = True
            
            if should_show:
                badge.show()
            else:
                badge.hide()
                
            try:
                # Stats are keyed by integer seat numbers in the tracker
                i = int(seat_id)
                player = tracker.session_stats.get_seat(i)
                player_name = tracker.seat_players.get(i, f"Seat {i}")
                if player.hands_played >= 0:
                    badge.update_stats(player.vpip_percent, player.pfr_percent, player.hands_played, player_name=player_name)
            except (ValueError, TypeError):
                continue
                
        # Hero stats (Lifetime)
        if tracker.hero_stats and tracker.hero_stats.hands_played >= 0:
            hero_display_name = "Hero"
            if hasattr(tracker, 'hero_seat') and tracker.hero_seat in tracker.seat_players:
                hero_display_name = tracker.seat_players[tracker.hero_seat]
            self.badges["hero"].update_stats(
                tracker.hero_stats.vpip_percent, 
                tracker.hero_stats.pfr_percent, 
                tracker.hero_stats.hands_played, 
                hero_lifetime=True, 
                player_name=f"{hero_display_name} (Lifetime)"
            )
            
    def shutdown(self):
        for b in self.badges.values():
            b.close()
