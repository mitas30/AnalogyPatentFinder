from __future__ import annotations

import argparse
from pathlib import Path

from tools._bootstrap import activate_server_context, resolve_repo_path


def _count_input_files(input_path: Path) -> int:
    return sum(1 for path in input_path.rglob("*") if path.is_file())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import raw patent PDF data into MongoDB."
    )
    parser.add_argument("--input", required=True, help="Input folder under the repo root or an absolute path.")
    parser.add_argument("--processed", help="Folder for processed/error files.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually write extracted patent data to MongoDB and move processed files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = resolve_repo_path(args.input)
    processed_path = resolve_repo_path(args.processed) if args.processed else None

    if not input_path.exists() or not input_path.is_dir():
        parser.error(f"--input must be an existing directory: {input_path}")
    if args.write and processed_path is None:
        parser.error("--processed is required when --write is set")

    if not args.write:
        file_count = _count_input_files(input_path)
        print(f"Dry run: {file_count} file(s) would be scanned from {input_path}")
        return 0

    activate_server_context()
    from setting_log.logging_config import setup_logging
    from tools.operations import pdfDataProcessor

    setup_logging()
    processor = pdfDataProcessor(str(input_path), str(processed_path))
    processor.batch_extract_patent_datas(is_test=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
