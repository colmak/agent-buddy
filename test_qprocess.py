import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QProcess

app = QApplication(sys.argv)
p = QProcess()
p.readyReadStandardOutput.connect(lambda: print("OUT:", p.readAllStandardOutput().data()))
p.readyReadStandardError.connect(lambda: print("ERR:", p.readAllStandardError().data()))
p.finished.connect(lambda: app.quit())
p.start("script", ["-q", "/dev/null", "-c", "echo hello"])
app.exec()
