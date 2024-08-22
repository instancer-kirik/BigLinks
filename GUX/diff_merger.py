import difflib
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSplitter, QTextEdit, QScrollArea, QFrame, QFileDialog, QStatusBar, QCheckBox, 
    QPlainTextEdit, QApplication)
from PyQt6.QtGui import QTextCharFormat, QSyntaxHighlighter, QColor, QKeySequence, QShortcut, QTextCursor, QFont, QFontInfo, QFontMetrics, QPainter
from PyQt6.QtCore import Qt, QRegularExpression, QEvent, QSize, QRect, pyqtSignal
import re
from GUX.code_editor import CompEditor

class DiffMergerWidget(QWidget):
    key_symbols = ['def', 'class', 'import']

    def __init__(self):
        super().__init__()
        self.isFullScreen = True
        self.diff_data = {}
        self.current_diff_index = -1
        self.current_line_index = 0
        
        self.initUI()

    def initUI(self):
        self.setMinimumSize(1200, 800)
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)

        # Initialize text editors
        self.x_box = CompEditor()
        self.y_box = CompEditor()
        self.result_box = CompEditor()

        # Create a fullscreen button
        self.fullscreen_button = QPushButton("Fullscreen", self)
        self.fullscreen_button.setMaximumWidth(100)
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)

        # Add the button to the layout
        main_layout.addWidget(self.fullscreen_button)

        # Scroll synchronization
        self.x_box.text_edit.verticalScrollBar().valueChanged.connect(self.sync_scrolls)
        self.y_box.text_edit.verticalScrollBar().valueChanged.connect(self.sync_scrolls)
        self.result_box.text_edit.verticalScrollBar().valueChanged.connect(self.sync_scrolls)

        # Top layout for editors and buttons
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.create_text_input_area("X", self.x_box))
        top_layout.addWidget(self.create_text_input_area("Y", self.y_box))

        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addWidget(QPushButton('Show Diff', clicked=self.show_diff))
        button_layout.addWidget(QPushButton('Clear Result', clicked=self.clear_diff_layout))
        button_layout.addWidget(QPushButton('Save Result', clicked=self.save_result_text))

        self.use_original_order_checkbox = QCheckBox("Use Original File Key Order")
        button_layout.addWidget(self.use_original_order_checkbox)

        top_layout.addLayout(button_layout)
        main_layout.addLayout(top_layout)

        # Diff layout with scroll area
        self.diff_layout = QVBoxLayout()
        diff_widget = QWidget()
        diff_widget.setLayout(self.diff_layout)
        diff_widget.setMinimumSize(600, 300)

        self.diff_scroll_area = QScrollArea()
        self.diff_scroll_area.setWidgetResizable(True)
        self.diff_scroll_area.setWidget(diff_widget)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.addWidget(self.diff_scroll_area)
        self.splitter.addWidget(self.result_box)

        main_layout.addWidget(self.splitter)

        self.status_bar = QStatusBar()
        main_layout.addWidget(self.status_bar)

        self.setLayout(main_layout)
        self.setup_shortcuts()

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+O"), self, self.load_original_text)
        QShortcut(QKeySequence("Ctrl+N"), self, self.load_new_text)
        QShortcut(QKeySequence("Ctrl+D"), self, self.show_diff)
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_result_text)
        QShortcut(QKeySequence("Ctrl+Up"), self, self.scroll_to_previous_diff)
        QShortcut(QKeySequence("Ctrl+Down"), self, self.scroll_to_next_diff)

    def toggle_fullscreen(self):
        main_window = self.window()
        if main_window.isFullScreen():
            main_window.showNormal()
            self.fullscreen_button.setText("Fullscreen")
        else:
            main_window.showFullScreen()
            self.fullscreen_button.setText("Exit Fullscreen")

    def sync_scrolls(self, value):
        """Synchronize the scroll positions of the text editors."""
        sender = self.sender()
        if sender == self.x_box.text_edit.verticalScrollBar():
            self.y_box.text_edit.verticalScrollBar().setValue(value)
            self.result_box.text_edit.verticalScrollBar().setValue(value)
        elif sender == self.y_box.text_edit.verticalScrollBar():
            self.x_box.text_edit.verticalScrollBar().setValue(value)
            self.result_box.text_edit.verticalScrollBar().setValue(value)
        elif sender == self.result_box.text_edit.verticalScrollBar():
            self.x_box.text_edit.verticalScrollBar().setValue(value)
            self.y_box.text_edit.verticalScrollBar().setValue(value)

    def scroll_to_previous_diff(self):
        if self.current_diff_index > 0:
            self.current_diff_index -= 1
            self.scroll_to_diff_index(self.current_diff_index)
            self.update_position_indicators()

    def scroll_to_next_diff(self):
        if self.current_diff_index < len(self.diff_data) - 1:
            self.current_diff_index += 1
            self.scroll_to_diff_index(self.current_diff_index)
            self.update_position_indicators()

    def scroll_to_diff_index(self, index):
        key = list(self.diff_data.keys())[index]
        self.scroll_to_diff_key(key)
        self.current_line_index = 0  # Reset the line index when scrolling to a new diff
        self.update_position_indicators()
    def load_original_text(self):
        file_dialog = QFileDialog()
        original_file, _ = file_dialog.getOpenFileName(self, "Open Original File", "", "Text Files (*.txt)")
        if original_file:
            with open(original_file, 'r') as file:
                self.x_box.text_edit.setPlainText(file.read())

    def load_new_text(self):
        file_dialog = QFileDialog()
        new_file, _ = file_dialog.getOpenFileName(self, "Open New File", "", "Text Files (*.txt)")
        if new_file:
            with open(new_file, 'r') as file:
                self.y_box.text_edit.setPlainText(file.read())

    def show_diff(self):
        self.clear_diff_layout()
        self.result_box.text_edit.clear()
        self.diff_data.clear()  # Clear previous diff data

        original_blocks = self.extract_code_blocks(self.x_box.text_edit.toPlainText())
        new_blocks = self.extract_code_blocks(self.y_box.text_edit.toPlainText())

        use_original_order = self.use_original_order_checkbox.isChecked()
        all_keys = list(original_blocks.keys()) if use_original_order else list(new_blocks.keys())

        for key in all_keys:
            self.compare_code_blocks(key, original_blocks.get(key, {}), new_blocks.get(key, {}))

        self.current_diff_index = 0
        self.current_line_index = 0
        self.add_all_matching_blocks()
        self.update_position_indicators()

        # Ensure the diff view is updated
        self.diff_scroll_area.widget().update()

    def create_text_input_area(self, label, text_edit):
        layout = QVBoxLayout()
        layout.addWidget(QLabel(label))
        layout.addWidget(text_edit)
        if label == 'X':
            self.add_and_next_x = QPushButton("Add and Next (X)")
            self.add_and_next_x.clicked.connect(lambda: self.on_add_and_next_clicked('left'))
            layout.addWidget(self.add_and_next_x)
        if label == 'Y':
            self.add_and_next_y = QPushButton("Add and Next (Y)")
            self.add_and_next_y.clicked.connect(lambda: self.on_add_and_next_clicked('right'))
            layout.addWidget(self.add_and_next_y)
        container = QWidget()
        container.setLayout(layout)
        return container

    def extract_code_blocks(self, text):
        blocks = {}
        lines = text.split('\n')
        current_block = []
        current_key = 'global'
        start_line = 0

        for i, line in enumerate(lines):
            if line.strip().startswith(tuple(self.key_symbols)):
                if current_block:
                    blocks[current_key] = {
                        'content': '\n'.join(current_block),
                        'start_line': start_line,
                        'end_line': i - 1
                    }
                current_key = line.strip()
                current_block = [line]
                start_line = i
            else:
                current_block.append(line)

        if current_block:
            blocks[current_key] = {
                'content': '\n'.join(current_block),
                'start_line': start_line,
                'end_line': len(lines) - 1
            }
        return blocks

    def on_add_and_next_clicked(self, side):
        """Handle adding lines and scrolling to the next conflict."""
        if self.current_diff_index >= len(self.diff_data):
            self.status_bar.showMessage("No more conflicts")
            return

        # Process through all diff blocks until the next conflict of the selected side
        while self.current_diff_index < len(self.diff_data):
            key = list(self.diff_data.keys())[self.current_diff_index]
            diff_data = self.diff_data[key]
            diff = diff_data['diff']

            conflict_found = False
            lines_to_add = []

            for i in range(self.current_line_index, len(diff)):
                line = diff[i]
                if line.startswith(' '):  # Matching line
                    lines_to_add.append(line[1:])
                elif (side == 'left' and line.startswith('-')) or (side == 'right' and line.startswith('+')):
                    lines_to_add.append(line[1:])
                else:  # Conflict of the other side encountered
                    conflict_found = True
                    self.current_line_index = i
                    break

            # Add the collected lines to the result box
            self.result_box.text_edit.insertPlainText('\n'.join(lines_to_add) + '\n')

            if conflict_found:
                break
            else:
                # Move to the next diff block
                self.current_diff_index += 1
                self.current_line_index = 0  # Reset line index for the next block

        # Update indicators for the next block
        self.update_position_indicators()

        # If we've processed all blocks, update the status
        if self.current_diff_index >= len(self.diff_data):
            self.status_bar.showMessage("All conflicts resolved")
        else:
            self.scroll_to_diff_index(self.current_diff_index)
    def compare_code_blocks(self, key, original_block, new_block):
        original_lines = original_block.get('content', '').split('\n')
        new_lines = new_block.get('content', '').split('\n')

        diff = list(difflib.ndiff(original_lines, new_lines))
        is_conflict = any(line.startswith('- ') or line.startswith('+ ') for line in diff)

        if is_conflict:
            self.diff_data[key] = {
                'original': original_block,
                'new': new_block,
                'diff': diff
            }

            self.add_diff_key_to_layout(key)
    def add_all_matching_blocks(self):
        """Add all matching blocks at the start and between conflicts."""
        for key in self.diff_data.keys():
            diff = self.diff_data[key]['diff']
            for line in diff:
                if line.startswith(' '):  # Matching line
                    self.result_box.text_edit.insertPlainText(line[1:] + '\n')
                else:
                    # Stop at the first non-matching line (conflict)
                    return
    
    def add_diff_key_to_layout(self, key):
        button = QPushButton(f'Conflict: {key}', self)
        button.clicked.connect(lambda _, k=key: self.scroll_to_diff_key(k))
        self.diff_layout.addWidget(button)

    def scroll_to_diff_key(self, key):
        self.current_diff_index = list(self.diff_data.keys()).index(key)
        diff_data = self.diff_data[key]
        start_line_x = diff_data['original']['start_line']
        start_line_y = diff_data['new']['start_line']

        self.x_box.text_edit.verticalScrollBar().setValue(start_line_x)
        self.y_box.text_edit.verticalScrollBar().setValue(start_line_y)

        self.current_line_index = 0  # Reset the line index when scrolling to a new diff
        self.update_position_indicators()

    def update_position_indicators(self):
        if self.current_diff_index >= len(self.diff_data):
            return

        key = list(self.diff_data.keys())[self.current_diff_index]
        diff_data = self.diff_data[key]

        start_line_x = diff_data['original']['start_line']
        end_line_x = diff_data['original']['end_line']
        self.x_box.update_line_indicators(start_line_x, end_line_x)

        start_line_y = diff_data['new']['start_line']
        end_line_y = diff_data['new']['end_line']
        self.y_box.update_line_indicators(start_line_y, end_line_y)

    def clear_diff_layout(self):
        """Clear the layout and reset the diff data."""
        for i in reversed(range(self.diff_layout.count())):
            widget_to_remove = self.diff_layout.itemAt(i).widget()
            self.diff_layout.removeWidget(widget_to_remove)
            widget_to_remove.setParent(None)

        self.diff_data.clear()

    def save_result_text(self):
        file_dialog = QFileDialog()
        save_file, _ = file_dialog.getSaveFileName(self, "Save Result", "", "Text Files (*.txt)")
        if save_file:
            with open(save_file, 'w') as file:
                file.write(self.result_box.text_edit.toPlainText())

if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    window = DiffMergerWidget()
    window.show()
    sys.exit(app.exec())
