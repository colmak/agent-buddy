#!/usr/bin/env python3
import sys
import os
import subprocess
import re
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QInputDialog, QMessageBox, QTextEdit, QLineEdit,
    QSplitter
)
from PyQt6.QtCore import Qt, QProcess

from PyQt6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox

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

AGENT_COMMAND = os.environ.get("AGENT_COMMAND", "claude")

class AgentSession:
    def __init__(self, name, process):
        self.name = name
        self.process = process
        self.output_buffer = ""

class AgentBuddyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Agent Buddy")
        self.resize(1000, 700)
        self.sessions = {} # name -> AgentSession
        self.current_session = None

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # Left Panel (Session List)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Style the left panel to look slightly better
        self.session_list = QListWidget()
        self.session_list.currentItemChanged.connect(self.on_session_selected)
        left_layout.addWidget(self.session_list)

        btn_layout = QHBoxLayout()
        self.btn_create = QPushButton("Create Session")
        self.btn_create.clicked.connect(self.create_session)
        self.btn_kill = QPushButton("Kill Session")
        self.btn_kill.clicked.connect(self.kill_session)
        btn_layout.addWidget(self.btn_create)
        btn_layout.addWidget(self.btn_kill)
        left_layout.addLayout(btn_layout)

        splitter.addWidget(left_widget)

        # Right Panel (Terminal / Chat)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        # Apply a simple dark style and mono font
        self.terminal_output.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Courier New', Courier, monospace;
                font-size: 14px;
                padding: 10px;
                border: none;
            }
        """)
        right_layout.addWidget(self.terminal_output)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your message here and press Enter...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                color: #ffffff;
                font-size: 14px;
                padding: 8px;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
            }
        """)
        self.input_field.returnPressed.connect(self.send_input)
        right_layout.addWidget(self.input_field)

        splitter.addWidget(right_widget)
        splitter.setSizes([250, 750])

    def create_session(self):
        dialog = CreateSessionDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
            
        name, command = dialog.get_data()
        if not name or not command:
            QMessageBox.warning(self, "Error", "Name and command cannot be empty.")
            return
        
        if name in self.sessions:
            QMessageBox.warning(self, "Error", f"Session '{name}' already exists.")
            return

        # Check for git repo and create worktree if possible
        work_dir = os.getcwd()
        has_git = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], capture_output=True).returncode == 0
        
        if has_git:
            branch_name = f"agent-{name}"
            worktree_dir = os.path.abspath(os.path.join("..", ".ab-worktrees", name))
            os.makedirs(os.path.join("..", ".ab-worktrees"), exist_ok=True)
            
            res = subprocess.run(["git", "worktree", "add", "-b", branch_name, worktree_dir], capture_output=True, text=True)
            if res.returncode == 0:
                work_dir = worktree_dir
            else:
                QMessageBox.warning(self, "Worktree Error", f"Failed to create git worktree. Starting in current dir.\n{res.stderr}")

        # Start process with a PTY using 'script' so interactive CLI tools don't exit
        process = QProcess(self)
        process.setWorkingDirectory(work_dir)
        process.setProgram("script")
        process.setArguments(["-q", "/dev/null", "-c", command])
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        
        session = AgentSession(name, process)
        self.sessions[name] = session
        
        process.readyReadStandardOutput.connect(lambda s=name: self.on_process_output(s))
        process.finished.connect(lambda exit_code, exit_status, s=name: self.on_process_finished(s))
        
        process.start()

        self.session_list.addItem(name)
        items = self.session_list.findItems(name, Qt.MatchFlag.MatchExactly)
        if items:
            self.session_list.setCurrentItem(items[0])

    def kill_session(self):
        current_item = self.session_list.currentItem()
        if not current_item:
            return
        name = current_item.text()
        
        reply = QMessageBox.question(self, "Confirm Kill", f"Are you sure you want to kill session '{name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            session = self.sessions.get(name)
            if session:
                session.process.kill()
                session.process.waitForFinished()
                del self.sessions[name]
                
            self.session_list.takeItem(self.session_list.row(current_item))
            self.terminal_output.clear()
            self.current_session = None

            # Cleanup worktree
            worktree_dir = os.path.abspath(os.path.join("..", ".ab-worktrees", name))
            if os.path.exists(worktree_dir):
                subprocess.run(["git", "worktree", "remove", worktree_dir, "--force"])

    def on_session_selected(self, current, previous):
        if not current:
            self.current_session = None
            self.terminal_output.clear()
            return
        name = current.text()
        self.current_session = name
        session = self.sessions.get(name)
        if session:
            self.terminal_output.setPlainText(session.output_buffer)
            self.terminal_output.verticalScrollBar().setValue(self.terminal_output.verticalScrollBar().maximum())

    def on_process_output(self, session_name):
        session = self.sessions.get(session_name)
        if not session:
            return
        
        data = session.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        
        # Remove simple ANSI escape codes for basic display
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        data = ansi_escape.sub('', data)
        
        session.output_buffer += data
        
        if self.current_session == session_name:
            scrollbar = self.terminal_output.verticalScrollBar()
            at_bottom = scrollbar.value() == scrollbar.maximum()
            
            # Using insertPlainText to avoid full re-rendering
            cursor = self.terminal_output.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.terminal_output.setTextCursor(cursor)
            self.terminal_output.insertPlainText(data)
            
            if at_bottom:
                scrollbar.setValue(scrollbar.maximum())

    def on_process_finished(self, session_name):
        session = self.sessions.get(session_name)
        if session:
            msg = "\n[Process finished]\n"
            session.output_buffer += msg
            if self.current_session == session_name:
                cursor = self.terminal_output.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                self.terminal_output.setTextCursor(cursor)
                self.terminal_output.insertPlainText(msg)

    def send_input(self):
        text = self.input_field.text()
        self.input_field.clear()
        
        if not self.current_session:
            return
            
        session = self.sessions.get(self.current_session)
        if session and session.process.state() == QProcess.ProcessState.Running:
            # Echo input locally
            echo_msg = f"\n> {text}\n"
            session.output_buffer += echo_msg
            
            cursor = self.terminal_output.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.terminal_output.setTextCursor(cursor)
            self.terminal_output.insertPlainText(echo_msg)
            
            # Send to process
            session.process.write((text + "\n").encode("utf-8"))

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Simple dark theme palette for the application
    from PyQt6.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(42, 42, 42))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(66, 66, 66))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(palette)

    window = AgentBuddyWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
