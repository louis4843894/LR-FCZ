"""Validate equipment rows in an already decoded SQLite copy; never decrypt or infer fields."""
from __future__ import annotations
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def validate(source: Path, table: str, name_column: str | None, name_key: str | None,
             id_column: str | None, star_column: str | None, limit: int) -> dict:
    source = source.resolve(strict=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    connection = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('PRAGMA query_only=ON')
        integrity = [row[0] for row in connection.execute('PRAGMA integrity_check')]
        if integrity != ['ok']:
            raise ValueError('SQLite integrity_check failed')
        schema = connection.execute(
            'SELECT sql FROM sqlite_master WHERE type=? AND name=?', ('table', table)
        ).fetchone()
        if schema is None:
            raise ValueError(f'Equipment table does not exist: {table}')
        columns = [dict(row) for row in connection.execute('PRAGMA table_info(' + quote_identifier(table) + ')')]
        names = {row['name'] for row in columns}
        for column in (name_column, id_column, star_column):
            if column is not None and column not in names:
                raise ValueError(f'Explicit column does not exist: {column}')
        query = 'SELECT * FROM ' + quote_identifier(table)
        parameters: list = []
        if name_key is not None:
            if name_column is None:
                raise ValueError('--name-key requires --name-column')
            query += ' WHERE ' + quote_identifier(name_column) + ' = ?'
            parameters.append(name_key)
        query += ' LIMIT ?'
        parameters.append(limit)
        rows = [dict(row) for row in connection.execute(query, parameters)]
        def to_json(value):
            if isinstance(value, bytes):
                return {'sqliteBlobHex': value.hex(), 'byteLength': len(value)}
            return value
        rows = [{key: to_json(value) for key, value in row.items()} for row in rows]
        total = connection.execute('SELECT count(*) FROM ' + quote_identifier(table)).fetchone()[0]
        result = {
            'source': str(source), 'sourceSha256': digest,
            'outerDecryptionVerifiedByThisTool': False,
            'sqliteIntegrity': integrity, 'table': table, 'schemaSql': schema[0],
            'columns': columns, 'tableRowCount': total, 'sampleCount': len(rows),
            'sampleRows': rows,
            'explicitFieldSelection': {'id': id_column, 'star': star_column, 'nameKey': name_column},
            'semanticsWarning': 'Column selection is supplied by caller; this tool does not prove game semantics.'
        }
        if id_column:
            ids = [row[id_column] for row in rows]
            if any(value is None for value in ids):
                raise ValueError('Sample contains a NULL equipment ID')
            if len({json.dumps(value, sort_keys=True) for value in ids}) != len(ids):
                raise ValueError('Sample contains duplicate equipment IDs')
        if star_column and any(not isinstance(row[star_column], int) for row in rows):
            raise ValueError('Selected star field contains a non-integer; review schema and semantics')
        return result
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--table', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--name-column')
    parser.add_argument('--name-key')
    parser.add_argument('--id-column')
    parser.add_argument('--star-column')
    parser.add_argument('--limit', type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error('--limit must be between 1 and 100')
    if args.output.resolve() == args.source.resolve():
        parser.error('Output must not overwrite source')
    result = validate(args.source, args.table, args.name_column, args.name_key,
                      args.id_column, args.star_column, args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'SQLite validated; table rows={result["tableRowCount"]}; samples={result["sampleCount"]}; report={args.output}')


if __name__ == '__main__':
    main()
