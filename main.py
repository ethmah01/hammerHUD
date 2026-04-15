import sys
import os
import logging
import traceback
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer

from core.config import ConfigManager
from parser.tracker import SessionTracker
from ui.overlay import OverlayManager
from ui.settings import SettingsWindow
from core.memory_reader import IgnitionMemoryReader
from core.hand_logger import HandLogger

# Set up logging to file
logging.basicConfig(
    filename='poker_hud_debug.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def exception_hook(exctype, value, tb):
    """Global exception handler to log crashes."""
    err_msg = "".join(traceback.format_exception(exctype, value, tb))
    logging.critical("Uncaught Exception:\n" + err_msg)
    print(err_msg, file=sys.stderr)
    sys.exit(1)

sys.excepthook = exception_hook

class AppSignals(QObject):
    hand_completed = pyqtSignal(dict)

def main():
    app = QApplication(sys.argv)
    
    config = ConfigManager()
    tracker = SessionTracker()
    overlay = OverlayManager(config, tracker)
    
    # Initialize Hand Logger
    save_path = config.get("hand_history_save_path", "")
    hand_logger = HandLogger(save_path)
    
    signals = AppSignals()
    mem_reader = None
    
    @pyqtSlot(dict)
    def on_hand_completed(hand_data):
        """Called on main thread when a hand completes."""
        try:
            if tracker.process_hand_event(hand_data):
                # Save to disk
                hand_logger.log_hand(hand_data)
                # Update UI visibility using the authoritative confirmed seated set
                confirmed = hand_data.get('confirmed_seated', hand_data.get('active_seats', []))
                overlay.update_session(tracker, active_seats=confirmed)
        except Exception as e:
            logging.error(f"Error in on_hand_completed: {e}\n{traceback.format_exc()}")
    
    signals.hand_completed.connect(on_hand_completed)
    
    def hand_callback(hand_data):
        """Thread-safe callback from memory reader → emits signal."""
        signals.hand_completed.emit(hand_data)
    
    def start_reader() -> bool:
        """Start the memory reader."""
        nonlocal mem_reader
        try:
            if mem_reader:
                mem_reader.stop()
            
            mem_reader = IgnitionMemoryReader(hand_callback)
            mem_reader.start()
            print("main: Memory reader started. Scanning for Ignition...")
            return True
        except Exception as e:
            print(f"main: CRITICAL STARTUP ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # Auto-start the memory reader
    start_reader()
    
    # Periodic status update for the settings window
    def update_status():
        if mem_reader and hasattr(settings, 'update_reader_status'):
            info = mem_reader.game_info
            settings.update_reader_status(info)
            
            # Auto-detect and set table size
            capacity = info.get('table_capacity')
            if capacity and capacity != overlay.table_size:
                logging.info(f"main: Auto-updating table size to {capacity}")
                overlay.set_table_size(capacity, tracker)
                # Update settings UI combo if it exists
                if hasattr(settings, 'size_combo'):
                    settings.size_combo.setCurrentText(f"{capacity}-Max")
            
            # Sync table size, but don't force a full update_session here 
            # as it will be driven by hand completion events or protocol snapshots.

    status_timer = QTimer()
    status_timer.timeout.connect(update_status)
    status_timer.start(3000)  # Update status every 3 seconds
    
    # Detect hero seat from the memory reader's game event
    def detect_hero_from_events():
        """Try to detect hero seat from the game protocol."""
        if mem_reader and mem_reader.game_info.get('active_seats'):
            # Hero seat detection is done via CO_SELECT_RES_V2 messages
            # which only appear for OUR actions. For now, we'll use config.
            hero = config.get("hero_seat", None)
            if hero:
                tracker.set_hero_seat(hero)
    
    hero_timer = QTimer()
    hero_timer.timeout.connect(detect_hero_from_events)
    hero_timer.start(5000)
    
    settings = SettingsWindow(config, tracker, start_reader, overlay, hand_logger)
    settings.show()
    
    exit_code = app.exec()
    
    # Cleanup
    if mem_reader:
        mem_reader.stop()
    overlay.shutdown()
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
