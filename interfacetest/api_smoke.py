#!/usr/bin/env python3
import argparse
import json

from quick_apis import quick_openai_message, quick_perplexity_search


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test quick APIs used by interfacetest UI demos")
    parser.add_argument("--quick", help="Prompt for quick message API")
    parser.add_argument("--search", help="Query for internet search API")
    args = parser.parse_args()

    if not args.quick and not args.search:
        parser.error("Provide at least one of --quick or --search")

    if args.quick:
        result = quick_openai_message(args.quick)
        print("QUICK RESULT")
        print(json.dumps(result, indent=2))

    if args.search:
        result = quick_perplexity_search(args.search)
        print("SEARCH RESULT")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
