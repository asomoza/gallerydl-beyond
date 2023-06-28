from PyQt6.QtWidgets import QTableView, QMenu
from PyQt6.QtGui import QAction, QColor

white_color = QColor(227, 226, 224)

class ProcessedTableView(QTableView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue_table = None
        self.message_window = None

    def set_queue_table(self, queue_table):
        self.queue_table = queue_table

    def set_message_window(self, message_window):
        self.message_window = message_window        

    def contextMenuEvent(self, event):
        # Create a menu
        menu = QMenu(self)

        # Add an action to set the processed field to 0
        set_processed_action = QAction("Send to queue", self)
        set_processed_action.triggered.connect(self.set_processed_to_zero)
        menu.addAction(set_processed_action)

        # Show the menu at the cursor position
        menu.popup(event.globalPos())

    def set_processed_to_zero(self):
        # Get the selected row
        indexes = self.selectionModel().selectedRows()

        if indexes:
            # Get the row numbers of the selected rows
            rows = [index.row() for index in indexes]

            # Set the processed field to 0 for all selected rows
            for row in rows:
                # Get the index of the "url" field in this row
                url_index = self.model().index(row, 1)

                # Get the value of the "url" field
                url = self.model().data(url_index)

                record = self.model().record(row)
                record.setValue('processed', 0)
                self.model().setRecord(row, record)

                self.message_window.setTextColor(white_color)
                self.message_window.append(f"Sent {url} to queue again.")

            # Apply the changes to the database
            self.model().submitAll()

            # Refresh the model
            self.model().select()

            # Refresh the other table view
            self.queue_table.model().select()