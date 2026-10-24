"""Command-line interface for TestBridge."""

from __future__ import annotations

import argparse
from pathlib import Path

from testbridge.build import build_pack
from testbridge.content.repository import list_packs
from testbridge.contract.validator import validate_pack
from testbridge.evidence.store import EvidenceStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tb")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate a content pack")
    validate.add_argument("pack")

    build = sub.add_parser("build", help="build standalone lessons")
    build.add_argument("pack")
    build.add_argument("--out", default="dist")
    build.add_argument("--lesson", default=None)

    serve = sub.add_parser("serve", help="run the web app")
    serve.add_argument("pack")
    serve.add_argument("--db", default="data/testbridge.db")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    listing = sub.add_parser("list", help="list packs under a root")
    listing.add_argument("root", default="content-packs", nargs="?")

    export = sub.add_parser("evidence-export")
    export.add_argument("db")
    export.add_argument("out")

    import_cmd = sub.add_parser("evidence-import")
    import_cmd.add_argument("db")
    import_cmd.add_argument("path")

    args = parser.parse_args(argv)

    if args.command == "validate":
        report = validate_pack(Path(args.pack))
        for issue in report.errors:
            print(f"ERROR {issue.code}: {issue.message}")
        for issue in report.warnings:
            print(f"WARN {issue.code}: {issue.message}")
        print(f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)")
        return 0 if report.ok else 1

    if args.command == "build":
        paths = build_pack(Path(args.pack), Path(args.out), args.lesson)
        for path in paths:
            print(path)
        return 0

    if args.command == "serve":
        import uvicorn

        from web.app import create_app

        uvicorn.run(create_app(Path(args.pack), Path(args.db)), host=args.host, port=args.port)
        return 0

    if args.command == "list":
        for info in list_packs(Path(args.root)):
            print(f"{info.meta.id}\t{info.meta.version}\t{info.path}")
        return 0

    if args.command == "evidence-export":
        count = EvidenceStore(Path(args.db)).export_jsonl(Path(args.out))
        print(f"exported {count}")
        return 0

    if args.command == "evidence-import":
        count = EvidenceStore(Path(args.db)).import_jsonl(Path(args.path))
        print(f"imported {count}")
        return 0

    return 1
