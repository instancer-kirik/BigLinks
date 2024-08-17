from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget, QTextEdit, QFileDialog,
                             QMessageBox, QInputDialog)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QBrush, QColor, QMouseEvent
import os
import sys

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        # Define formats
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QBrush(QColor(0, 0, 255)))
        keywords = ["def", "class", "import", "from", "return", "if", "else", "elif"]
        for keyword in keywords:
            pattern = rf"\b{keyword}\b"
            self.highlighting_rules.append((pattern, self.keyword_format))

        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QBrush(QColor(0, 128, 0)))
        self.highlighting_rules.append((r"#.*", self.comment_format))

        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QBrush(QColor(255, 0, 0)))
        self.highlighting_rules.append((r'"[^"]*"', self.string_format))
        self.highlighting_rules.append((r"'[^']*'", self.string_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            expression = QRegularExpression(pattern)
            iterator = expression.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)

class CodeEditorWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
       
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.check_for_unsaved_changes)
        self.layout.addWidget(self.tab_widget)
        self.setAcceptDrops(True)
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.start(300000)  # Auto-save every 5 minutes

        self.add_tab("Untitled")
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile()
                if os.path.isfile(file_path):
                    if event.keyboardModifiers() == Qt.KeyboardModifier.ControlModifier:
                        # Paste the path as text
                        self.paste_text(file_path)
                    else:
                        # Open the file
                        self.open_file(file_path)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def open_file(self, file_path):
        with open(file_path, 'r') as file:
            content = file.read()
        editor = self.tab_widget.currentWidget()
        editor.setPlainText(content)
        editor.setProperty("file_path", file_path)
        self.tab_widget.setTabText(self.tab_widget.currentIndex(), os.path.basename(file_path))

        # Apply syntax highlighting based on file extension
        if file_path.endswith('.py'):
            self.apply_syntax_highlighter(editor)

    def paste_text(self, text):
        cursor = self.tab_widget.currentWidget().textCursor()
        cursor.insertText(text)

    def add_tab(self, title, content=""):
        new_tab = QTextEdit()
        new_tab.setPlainText(content)
        new_tab.textChanged.connect(lambda: self.prompt_file_name(new_tab))
        new_tab.setProperty("file_path", None)
        self.tab_widget.addTab(new_tab, title)

    def close_tab(self, index):
        editor = self.tab_widget.widget(index)
        if editor.document().isModified():
            reply = QMessageBox.question(self, 'Save Changes', "The document has been modified. Do you want to save your changes?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Yes:
                self.save_file(editor)
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        self.tab_widget.removeTab(index)

    def check_for_unsaved_changes(self):
        current_editor = self.tab_widget.currentWidget()
        if current_editor and current_editor.document().isModified():
            self.save_file(current_editor)

    def save_file(self, editor=None):
        if not editor:
            editor = self.tab_widget.currentWidget()

        file_path = editor.property("file_path")
        if not file_path:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save File")
            if not file_path:
                return
            editor.setProperty("file_path", file_path)

        with open(file_path, 'w') as file:
            file.write(editor.toPlainText())
        editor.document().setModified(False)
        self.tab_widget.setTabText(self.tab_widget.indexOf(editor), os.path.basename(file_path))

    def auto_save(self):
        for i in range(self.tab_widget.count()):
            editor = self.tab_widget.widget(i)
            if editor.document().isModified():
                self.save_file(editor)

    def prompt_file_name(self, editor):
        if not editor.property("file_path") and editor.toPlainText():
            file_path, _ = QFileDialog.getSaveFileName(self, "Save File As")
            if file_path:
                editor.setProperty("file_path", file_path)
                self.save_file(editor)

    def apply_syntax_highlighter(self, editor):
        highlighter = PythonHighlighter(editor.document())
        editor.setProperty("highlighter", highlighter)

    def eventFilter(self, obj, event):
        if obj == self.tab_widget.tabBar():
            if event.type() == QMouseEvent.Type.Enter:
                self.scroll_timer.start(20)
            elif event.type() == QMouseEvent.Type.Leave:
                self.scroll_timer.stop()
                self.scroll_speed = 1
                self.scroll_direction = None
            elif event.type() == QMouseEvent.Type.MouseMove:
                self.update_scroll_speed(event.pos())
        return super().eventFilter(obj, event)

    def update_scroll_speed(self, pos):
        bar = self.tab_widget.tabBar()
        if pos.x() < 30:
            self.scroll_direction = -1
            self.scroll_speed = max(1, 30 - pos.x())
        elif pos.x() > bar.width() - 30:
            self.scroll_direction = 1
            self.scroll_speed = max(1, pos.x() - (bar.width() - 30))
        else:
            self.scroll_speed = 1
            self.scroll_direction = None

    def scroll_tabs(self):
        if self.scroll_direction is not None:
            bar = self.tab_widget.tabBar()
            current_index = self.tab_widget.currentIndex()
            new_index = (current_index + self.scroll_direction) % self.tab_widget.count()
            if new_index < 0:
                new_index = self.tab_widget.count() - 1
            self.tab_widget.setCurrentIndex(new_index)

            bar.scroll(self.scroll_direction * self.scroll_speed, 0)

    def wrap_tabs(self):
        current_index = self.tab_widget.currentIndex()
        self.tab_widget.setCurrentIndex((current_index + self.scroll_direction) % self.tab_widget.count())

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    editor = CodeEditorWidget()
    editor.show()
    sys.exit(app.exec())
