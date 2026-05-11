from __future__ import annotations

import argparse
import logging

from tools._bootstrap import activate_server_context


logger = logging.getLogger(__name__)


def _load_operations():
    activate_server_context()
    from setting_log.logging_config import setup_logging
    from tools import operations

    setup_logging()
    return operations


def cmd_add_heading(args: argparse.Namespace) -> int:
    operations = _load_operations()
    processor = operations.patentProcessor()
    if args.write:
        logger.info("Writing generated headings to MongoDB.")
        processor.add_heading(args.max_doc, is_process=True, is_write=True)
    else:
        logger.info("Dry run: showing documents that need headings. Use --write to update MongoDB.")
        processor.add_heading(args.max_doc, is_process=False, is_write=False)
    return 0


def cmd_batch_annotate_parameter(args: argparse.Namespace) -> int:
    operations = _load_operations()
    operations.gptBatch().batch_process("annotate_improvement_parameters", args.max_doc)
    return 0


def cmd_batch_categorize_function(args: argparse.Namespace) -> int:
    operations = _load_operations()
    operations.gptBatch().batch_process("categorize_functions", args.max_doc)
    return 0


def cmd_batch_add_heading(args: argparse.Namespace) -> int:
    operations = _load_operations()
    operations.gptBatch().batch_process("add_heading", args.max_doc)
    return 0


def cmd_ask_batch(args: argparse.Namespace) -> int:
    operations = _load_operations()
    completed = operations.gptBatch().ask_batch_result(args.batch_id)
    if not completed:
        logger.info("Batch is not completed yet.")
    return 0


def _write_batch_result(args: argparse.Namespace, process_type: str) -> int:
    operations = _load_operations()
    operations.gptBatch().write_batch_result_to_database(
        args.id_filename,
        args.output_filename,
        process_type,
        is_write=args.write,
    )
    if not args.write:
        logger.info("Dry run: batch result was checked only. Use --write to update MongoDB.")
    return 0


def cmd_check_batch_improve_params(args: argparse.Namespace) -> int:
    return _write_batch_result(args, "annotate_improvement_parameters")


def cmd_check_batch_categorize_function(args: argparse.Namespace) -> int:
    return _write_batch_result(args, "categorize_functions")


def cmd_check_batch_add_heading(args: argparse.Namespace) -> int:
    return _write_batch_result(args, "add_heading")


def cmd_aggregate(args: argparse.Namespace) -> int:
    operations = _load_operations()
    operator = operations.expOperator()
    if args.target == "parameters":
        operator.aggr_clasified_impr_params()
    else:
        operator.aggr_classified_function_classes()
    return 0


def cmd_make_abstracts(args: argparse.Namespace) -> int:
    operations = _load_operations()
    if args.write:
        operations.make_new_abstracts()
        return 0

    admin = operations.abstractAdmin(collection_name="patents")
    count = admin.collection.count_documents(
        {"parameters": {"$exists": True}, "does_insert_to_abst": {"$ne": True}}
    )
    logger.info("Dry run: %s patent document(s) would be transferred to abstracts. Use --write to update MongoDB.", count)
    return 0


def cmd_remove_duplicates(args: argparse.Namespace) -> int:
    operations = _load_operations()
    if args.write:
        operations.remove_all_documents_with_same_invent_name_and_problem()
        return 0

    cleaner = operations.patentCleaner("patents")
    duplicate_ids = cleaner.get_duplicate_ids()
    logger.info("Dry run: %s duplicate document(s) would be deleted. Use --write to delete them.", len(duplicate_ids))
    for duplicate_id in duplicate_ids[:20]:
        logger.info("Duplicate id: %s", duplicate_id)
    return 0


def cmd_update_full_url(args: argparse.Namespace) -> int:
    operations = _load_operations()
    if args.write:
        operations.update_documents_with_full_url(
            max_doc=args.max_doc,
            batch_size=args.batch_size,
            is_write=True,
        )
        return 0

    reader = operations.patentQuery(collection_name="patents")
    documents = reader.get_documents_without_full_url(args.max_doc)
    logger.info("Dry run: %s patent document(s) are missing full_url. Use --write to fetch and update URLs.", len(documents))
    for document in documents[:20]:
        logger.info("Missing full_url: id=%s apply_number=%s", document["id"], document["apply_number"])
    return 0


def _add_max_doc(parser: argparse.ArgumentParser, default: int | None) -> None:
    parser.add_argument("--max-doc", type=int, default=default, help="Maximum number of documents to process.")


def _add_batch_result_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("id_filename", help="ID memo filename without extension.")
    parser.add_argument("output_filename", help="Batch output filename without extension.")
    parser.add_argument("--write", action="store_true", help="Write checked batch results to MongoDB.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Administrative patent data operations.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_heading = subparsers.add_parser("add-heading", help="Show or generate missing headings.")
    _add_max_doc(add_heading, 15)
    add_heading.add_argument("--write", action="store_true", help="Generate headings and write them to MongoDB.")
    add_heading.set_defaults(func=cmd_add_heading)

    batch_annotate = subparsers.add_parser("batch-annotate-parameter", help="Submit an OpenAI batch for improvement parameters.")
    _add_max_doc(batch_annotate, 15)
    batch_annotate.set_defaults(func=cmd_batch_annotate_parameter)

    batch_categorize = subparsers.add_parser("batch-categorize-function", help="Submit an OpenAI batch for function classes.")
    _add_max_doc(batch_categorize, 50)
    batch_categorize.set_defaults(func=cmd_batch_categorize_function)

    batch_heading = subparsers.add_parser("batch-add-heading", help="Submit an OpenAI batch for headings.")
    _add_max_doc(batch_heading, 15)
    batch_heading.set_defaults(func=cmd_batch_add_heading)

    ask_batch = subparsers.add_parser("ask-batch", help="Fetch a completed OpenAI batch result.")
    ask_batch.add_argument("batch_id")
    ask_batch.set_defaults(func=cmd_ask_batch)

    check_improve = subparsers.add_parser("check-batch-improve-params", help="Check improvement-parameter batch output.")
    _add_batch_result_args(check_improve)
    check_improve.set_defaults(func=cmd_check_batch_improve_params)

    check_categorize = subparsers.add_parser("check-batch-categorize-function", help="Check function-class batch output.")
    _add_batch_result_args(check_categorize)
    check_categorize.set_defaults(func=cmd_check_batch_categorize_function)

    check_heading = subparsers.add_parser("check-batch-add-heading", help="Check heading batch output.")
    _add_batch_result_args(check_heading)
    check_heading.set_defaults(func=cmd_check_batch_add_heading)

    write_improve = subparsers.add_parser("write-batch-improve-params", help="Write improvement-parameter batch output.")
    _add_batch_result_args(write_improve)
    write_improve.set_defaults(func=cmd_check_batch_improve_params)

    write_categorize = subparsers.add_parser("write-batch-categorize-function", help="Write function-class batch output.")
    _add_batch_result_args(write_categorize)
    write_categorize.set_defaults(func=cmd_check_batch_categorize_function)

    write_heading = subparsers.add_parser("write-batch-add-heading", help="Write heading batch output.")
    _add_batch_result_args(write_heading)
    write_heading.set_defaults(func=cmd_check_batch_add_heading)

    aggregate = subparsers.add_parser("aggregate", help="Aggregate classified data.")
    aggregate.add_argument("target", choices=["parameters", "functions"])
    aggregate.set_defaults(func=cmd_aggregate)

    make_abstracts = subparsers.add_parser("make-abstracts", help="Create abstracts documents from patent parameters.")
    make_abstracts.add_argument("--write", action="store_true", help="Write new abstracts documents to MongoDB.")
    make_abstracts.set_defaults(func=cmd_make_abstracts)

    remove_duplicates = subparsers.add_parser("remove-duplicates", help="Remove duplicated patent documents.")
    remove_duplicates.add_argument("--write", action="store_true", help="Delete duplicate patent documents from MongoDB.")
    remove_duplicates.set_defaults(func=cmd_remove_duplicates)

    update_full_url = subparsers.add_parser("update-full-url", help="Fetch and store missing full patent URLs.")
    _add_max_doc(update_full_url, None)
    update_full_url.add_argument("--batch-size", type=int, default=50)
    update_full_url.add_argument("--write", action="store_true", help="Fetch URLs and write them to MongoDB.")
    update_full_url.set_defaults(func=cmd_update_full_url)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
