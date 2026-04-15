import os
import time
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class HandHistoryHandler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback
        self.processed_positions = {} # File path -> byte offset

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.txt'):
            self.process_file(event.src_path)

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.txt'):
            self.process_file(event.src_path)

    def process_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                pos = self.processed_positions.get(file_path, 0)
                f.seek(pos)
                new_data = f.read()
                if new_data:
                    self.processed_positions[file_path] = f.tell()
                    self.callback(new_data)
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")

class HHWatcher:
    """Watches the HandHistory directory in a background thread using Watchdog."""
    def __init__(self, directory, callback):
        self.directory = directory
        self.callback = callback
        self.observer = None

    def start(self):
        if not os.path.exists(self.directory):
            print(f"HHWatcher: Directory {self.directory} does not exist.")
            return

        event_handler = HandHistoryHandler(self.callback)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.directory, recursive=True)
        self.observer.start()
        print(f"HHWatcher started looking at {self.directory}")

    def stop(self):
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join()
            except RuntimeError:
                pass
            print("HHWatcher stopped.")
