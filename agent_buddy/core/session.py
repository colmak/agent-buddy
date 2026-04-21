from PyQt6.QtCore import QProcess

class AgentSession:
    def __init__(self, name: str, process: QProcess):
        self.name = name
        self.process = process
        self.output_buffer = ""
