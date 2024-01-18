from keboola.component.dao import TableDefinition
from keboola.csvwriter import ElasticDictWriter


class TableHandler:
    def __init__(self, table_definition: TableDefinition, writer: ElasticDictWriter):
        self.table_definition = table_definition
        self.writer = writer

    def close(self) -> None:
        self.writer.close()
        self.table_definition.columns = self.writer.fieldnames

    def write_rows(self, rows: list[dict]) -> None:
        self.writer.writerows(rows)

    def write_row(self, row: dict) -> None:
        self.writer.writerow(row)
