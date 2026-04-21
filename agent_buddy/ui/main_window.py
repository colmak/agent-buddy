import re
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QMessageBox, QTextEdit, QLineEdit,
    QSplitter, QDialog, QLabel, QTabWidget
)
from PyQt6.QtCore import Qt, QProcess, QEvent

from agent_buddy.core.session import AgentSession
from agent_buddy.core.workspace import create_worktree, remove_worktree
from agent_buddy.ui.dialogs import CreateSessionDialog

class AgentBuddyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Agent Buddy")
        self.resize(1000, 700)
        self.sessions = {} # name -> AgentSession
        self.current_session = None

        self._setup_ui()
        QApplication.instance().installEventFilter(self)

    def _setup_ui(self):
        # Global stylesheet (Dracula / Catppuccin Macchiato style)
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: 'Cascadia Code', 'Courier New', monospace;
            }
            QSplitter::handle {
                background-color: #313244;
            }
            QMessageBox {
                background-color: #181825;
            }
            QMessageBox QPushButton {
                background-color: #313244;
                padding: 6px 12px;
                border-radius: 4px;
            }
        """)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, stretch=1)

        # --- Left Panel ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        # Header
        header_layout = QHBoxLayout()
        lbl_instances = QLabel("Instances")
        lbl_instances.setStyleSheet("background-color: #b4befe; color: #11111b; padding: 4px 10px; font-weight: bold; border-radius: 4px;")
        lbl_auto = QLabel("auto-yes")
        lbl_auto.setStyleSheet("background-color: #cdd6f4; color: #11111b; padding: 4px 10px; font-weight: bold; border-radius: 4px;")
        header_layout.addWidget(lbl_instances)
        header_layout.addStretch()
        header_layout.addWidget(lbl_auto)
        left_layout.addLayout(header_layout)
        
        self.session_list = QListWidget()
        self.session_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
                margin-top: 15px;
            }
            QListWidget::item {
                padding: 12px;
                color: #a6adc8;
            }
            QListWidget::item:selected {
                background-color: #f5e0dc;
                color: #11111b;
                border-radius: 6px;
            }
        """)
        self.session_list.currentItemChanged.connect(self.on_session_selected)
        left_layout.addWidget(self.session_list)
        splitter.addWidget(left_widget)

        # --- Right Panel ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #cba6f7;
                border-radius: 6px;
                background-color: #181825;
            }
            QTabBar::tab {
                background: transparent;
                color: #a6adc8;
                padding: 8px 30px;
                margin-bottom: -1px;
            }
            QTabBar::tab:selected {
                color: #cba6f7;
                border-bottom: 2px solid #cba6f7;
            }
        """)
        
        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setStyleSheet("background-color: transparent; color: #cdd6f4; border: none; padding: 15px;")
        
        self.diff_output = QTextEdit()
        self.diff_output.setReadOnly(True)
        self.diff_output.setStyleSheet("background-color: transparent; color: #cdd6f4; border: none; padding: 15px;")
        
        self.tabs.addTab(self.terminal_output, "Preview")
        self.tabs.addTab(self.diff_output, "Diff")
        right_layout.addWidget(self.tabs, stretch=1)

        # Input Area
        input_layout = QHBoxLayout()
        prompt_lbl = QLabel("> ")
        prompt_lbl.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 16px;")
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("? for shortcuts")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 10px;
            }
            QLineEdit:focus {
                border: 1px solid #cba6f7;
            }
        """)
        self.input_field.returnPressed.connect(self.send_input)
        input_layout.addWidget(prompt_lbl)
        input_layout.addWidget(self.input_field)
        right_layout.addLayout(input_layout)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([350, 650])

        # --- Bottom Bar ---
        bottom_bar = QLabel("&nbsp;&nbsp;<span style='color:#a6e3a1'>n</span> new &nbsp;&nbsp;<span style='color:#f38ba8'>d</span> kill &nbsp;&nbsp;<span style='color:#89b4fa'>~/o</span> open &nbsp;&nbsp;<span style='color:#cba6f7'>s</span> submit PR &nbsp;&nbsp;<span style='color:#89b4fa'>c</span> checkout &nbsp;&nbsp;<span style='color:#bac2de'>tab</span> switch tab &nbsp;&nbsp;<span style='color:#bac2de'>q</span> quit ")
        bottom_bar.setTextFormat(Qt.TextFormat.RichText)
        bottom_bar.setStyleSheet("padding-top: 15px; color: #6c7086; font-size: 13px;")
        main_layout.addWidget(bottom_bar)

    def eventFilter(self, obj, event):
        # Handle global keyboard shortcuts when the input field is not focused
        if event.type() == QEvent.Type.KeyPress:
            if self.isActiveWindow():
                focus_widget = QApplication.focusWidget()
                if not isinstance(focus_widget, QLineEdit) and not isinstance(focus_widget, QTextEdit):
                    if event.key() == Qt.Key.Key_N:
                        self.create_session()
                        return True
                    elif event.key() == Qt.Key.Key_D:
                        self.kill_session()
                        return True
                    elif event.key() == Qt.Key.Key_Q:
                        self.close()
                        return True
                    elif event.key() == Qt.Key.Key_Tab:
                        current_tab = self.tabs.currentIndex()
                        self.tabs.setCurrentIndex((current_tab + 1) % self.tabs.count())
                        return True
        return super().eventFilter(obj, event)

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

        success, work_dir, error_msg = create_worktree(name)
        if not success and error_msg != "Not in a git repository.":
            QMessageBox.warning(self, "Worktree Error", f"Failed to create git worktree. Starting in current dir.\n{error_msg}")

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

        count = self.session_list.count() + 1
        formatted_text = f"{count}. {name}"
        from PyQt6.QtWidgets import QListWidgetItem
        item = QListWidgetItem(formatted_text)
        item.setData(Qt.ItemDataRole.UserRole, name)
        self.session_list.addItem(item)
        self.session_list.setCurrentItem(item)

    def kill_session(self):
        current_item = self.session_list.currentItem()
        if not current_item:
            return
        name = current_item.data(Qt.ItemDataRole.UserRole)
        
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

            remove_worktree(name)

    def on_session_selected(self, current, previous):
        if not current:
            self.current_session = None
            self.terminal_output.clear()
            return
        name = current.data(Qt.ItemDataRole.UserRole)
        self.current_session = name
        session = self.sessions.get(name)
        if session:
            self.terminal_output.setPlainText(session.get_display())
            self.terminal_output.verticalScrollBar().setValue(self.terminal_output.verticalScrollBar().maximum())

    def on_process_output(self, session_name):
        session = self.sessions.get(session_name)
        if not session:
            return
        
        raw_data = session.process.readAllStandardOutput().data()
        
        # Auto-reply to common terminal capability queries to unblock TUI apps
        if b"\x1b[6n" in raw_data:
            session.process.write(b"\x1b[1;1R")
        if b"\x1b[c" in raw_data or b"\x1b[>c" in raw_data:
            session.process.write(b"\x1b[?1;2c")
        if b"\x1b]10;?" in raw_data:
            session.process.write(b"\x1b]10;rgb:0000/0000/0000\x1b\\")
        if b"\x1b]11;?" in raw_data:
            session.process.write(b"\x1b]11;rgb:ffff/ffff/ffff\x1b\\")
            
        data = raw_data.decode("utf-8", errors="replace")
        session.feed(data)
        
        try:
            if self.current_session == session_name:
                scrollbar = self.terminal_output.verticalScrollBar()
                at_bottom = scrollbar.value() == scrollbar.maximum()
                
                self.terminal_output.setPlainText(session.get_display())
                
                if at_bottom:
                    scrollbar.setValue(scrollbar.maximum())
        except RuntimeError:
            pass # Widget deleted during app teardown

    def on_process_finished(self, session_name):
        session = self.sessions.get(session_name)
        if session:
            session.feed("\n[Process finished]\n")
            try:
                if self.current_session == session_name:
                    self.terminal_output.setPlainText(session.get_display())
                    scrollbar = self.terminal_output.verticalScrollBar()
                    scrollbar.setValue(scrollbar.maximum())
            except RuntimeError:
                pass # Widget deleted during app teardown

    def send_input(self):
        text = self.input_field.text()
        self.input_field.clear()
        
        if not self.current_session:
            return
            
        session = self.sessions.get(self.current_session)
        if session and session.process.state() == QProcess.ProcessState.Running:
            # Send \r instead of \n because TUI applications in raw mode expect Carriage Return
            session.process.write((text + "\r").encode("utf-8"))
