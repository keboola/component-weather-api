from csv import DictWriter
from io import TextIOWrapper

from keboola.component.dao import TableDefinition


class TableHandler:
    def __init__(self, table_definition: TableDefinition, file: TextIOWrapper, writer: DictWriter):
        self.table_definition = table_definition
        self.file = file
        self.writer = writer

    def close(self) -> None:
        self.file.close()

    def write_rows(self, rows: list[dict]) -> None:
        self.writer.writerows(rows)

    def write_row(self, row: dict) -> None:
        self.writer.writerow(row)
