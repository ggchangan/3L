from backend.migrations.holdings_entry_metadata import COLUMNS, migrate


class FakeDB:
    def __init__(self, existing=()):
        self.existing = set(existing)
        self.statements = []

    def execute_raw(self, sql):
        self.statements.append(sql)
        if sql == 'SHOW COLUMNS FROM holdings':
            return [{'Field': name} for name in self.existing]
        if sql.startswith('ALTER TABLE holdings ADD COLUMN '):
            self.existing.add(sql.split()[5])
        return []


def test_migration_adds_missing_columns_and_is_idempotent():
    db = FakeDB()

    assert set(migrate(db)) == set(COLUMNS)
    statement_count = len(db.statements)
    assert migrate(db) == []
    assert len(db.statements) == statement_count + 1
