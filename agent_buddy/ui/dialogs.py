import os
from PyQt6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QLineEdit

class CreateSessionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Session")
        self.layout = QFormLayout(self)
        
        self.name_input = QLineEdit(self)
        self.layout.addRow("Session Name:", self.name_input)
        
        self.command_input = QLineEdit(self)
        self.command_input.setText(os.environ.get("AGENT_COMMAND", "claude"))
        self.layout.addRow("Agent Command:", self.command_input)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def get_data(self):
        return self.name_input.text().strip(), self.command_input.text().strip()
