import pyte
from PyQt6.QtCore import QProcess

class AgentSession:
    def __init__(self, name: str, process: QProcess):
        self.name = name
        self.process = process
        self.screen = pyte.HistoryScreen(120, 30, history=1000)
        self.stream = pyte.Stream(self.screen)
        
    def feed(self, data: str):
        self.stream.feed(data)
        
    def get_display(self) -> str:
        # Include history lines and current screen lines
        history = ["".join(line[x].data for x in range(self.screen.columns)) for line in self.screen.history.top]
        current = self.screen.display
        
        # Combine and remove trailing empty lines to match terminal behavior
        all_lines = history + current
        while all_lines and not all_lines[-1].strip():
            all_lines.pop()
            
        return "\n".join(all_lines)
