from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

class ReviewTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        
        label = QLabel("No hands reviewed yet")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #cdcdcd; font-size: 16px;")
        
        layout.addWidget(label)
        self.setLayout(layout)
