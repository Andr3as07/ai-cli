#! /usr/bin/python

import sys
from typing import Any, Tuple
from openai import OpenAI
import os
import argparse

_clients = {}

def get_client(index: int = 0) -> Tuple[Any, str]:
    global _clients

    if index not in _clients:
        try:
            suffix = f"_{index}" if index > 0 else ""
            api_key = os.getenv("OPENAI_API_KEY" + suffix, "not-needed")
            api_url = os.getenv("OPENAI_BASE_URL" + suffix, "http://localhost:1234/v1")

            _clients[index] = OpenAI(base_url=api_url, api_key=api_key)
        except Exception as e:
           return None, f"Failed to create OpenAI client: {e}" 

    return _clients[index], None

def list_patterns():
    pattern_path = os.path.dirname(os.path.realpath(__file__)) + "/patterns"
    if not os.path.exists(pattern_path):
        print("Patterns directory not found", file=sys.stderr)
        exit(1)

    for filename in os.listdir(pattern_path):
        print(filename)

def perform_pattern(pattern: str, is_stream: bool, use_alternate: bool, temperature: float = 0.7, model: str = None):
    pattern_path = os.path.dirname(os.path.realpath(__file__)) + "/patterns/" + pattern
    if not os.path.exists(pattern_path):
        print(f"Pattern '{pattern}' not found", file=sys.stderr)
        exit(1)

    user_input = ""
    system_input = ""

    if os.path.isfile(pattern_path + "/system.md"):
        with open(pattern_path + "/system.md") as f:
            system_input = f.read()

    if system_input == "":
        print("Pattern didn't provide a system input", file=sys.stderr)
        exit(1)

    if os.path.isfile(pattern_path + "/user.md"):
        with open(pattern_path + "/user.md") as f:
            user_input = f.read()

    stdin = sys.stdin.read()

    if use_alternate:
        client, error = get_client(1)
    else:
        client, error = get_client(0)
    if error:
        print(error, file=sys.stderr)
        exit(1)

    # The model doesn't seem to matter at all
    if model is None:
        model = os.getenv("DEFAULT_MODEL", "gpt-4o")

    history = [
        {"role": "system", "content": system_input},
        {"role": "user", "content": user_input + stdin}
    ]

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=history,
            temperature=temperature,
            stream=is_stream,
        )

        if is_stream:
                for chunk in completion:
                    if chunk.choices[0].delta.content:
                        print(chunk.choices[0].delta.content, end="", flush=True)
        else:
            print(completion.choices[0].message.content)
    except KeyboardInterrupt:
        print("User interrupted execution", file=sys.stderr)
        exit(2)
    
    exit(0)

def main():
    pattern = None
    temperature = 0.7
    model = None
    is_stream = False
    use_alternate = False

    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--list-patterns", action='store_true', help="List available patterns")
    parser.add_argument("-s", "--stream", action='store_true', help="Stream output instead of waiting for completion")
    parser.add_argument("-a", "--alternate", action='store_true', help="Use the alternate server")
    parser.add_argument("-t", "--temperature", type=float, help="The temperature to use")
    parser.add_argument("-m", "--model", type=str, help="The model to use")
    parser.add_argument("PATTERN", type=str, help="The pattern to use", nargs='?')

    args = parser.parse_args()

    if args.list_patterns:
        list_patterns()
        exit(0)
    
    if args.PATTERN is not None:
        pattern = args.PATTERN

    if args.stream:
        is_stream = args.stream

    if args.alternate:
        use_alternate = args.alternate

    if args.temperature is not None:
        temperature = args.temperature

    if args.model is not None:
        model = args.model

    if pattern is None:
        parser.print_help()
        exit(0)

    perform_pattern(pattern, is_stream, use_alternate, temperature, model)

if __name__ == "__main__":
    main()