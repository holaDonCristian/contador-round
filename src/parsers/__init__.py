"""
File parsers — one module per file type.
Each parser exposes a single function:
    parse(file_bytes, filename) -> list[dict]
where each dict has keys:
    date, description, amount, merchant, location, transaction_type
The caller is responsible for adding category, account_id, source_file.
"""
