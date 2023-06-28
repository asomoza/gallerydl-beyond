from PyQt6.QtWidgets import QTableView, QMenu
from PyQt6.QtGui import QAction, QColor

red_color = QColor(255, 0, 0)

class QueueTableView(QTableView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_window = None

    def contextMenuEvent(self, event):
        # Create a menu
        menu = QMenu(self)

        # Add an action to remove the row
        set_processed_action = QAction("Remove", self)
        set_processed_action.triggered.connect(self.remove)
        menu.addAction(set_processed_action)

        # Show the menu at the cursor position
        menu.popup(event.globalPos())

    def set_message_window(self, message_window):
        self.message_window = message_window

    def remove(self):
        # Get the selected row
        indexes = self.selectionModel().selectedRows()

        if indexes:
            # Get the row numbers of the selected rows
            rows = [index.row() for index in indexes]

             # Delete the rows in reverse order
            for row in sorted(rows, reverse=True):
                # Get the index of the "url" field in this row
                url_index = self.model().index(row, 1)

                # Get the value of the "url" field
                url = self.model().data(url_index)

                self.model().removeRow(row)                
                self.message_window.setTextColor(red_color)
                self.message_window.append(f"Removed {url}")

            # Apply the changes to the database
            self.model().submitAll()

            # Refresh the model
            self.model().select()