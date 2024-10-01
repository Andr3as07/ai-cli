#! /usr/bin/python

import sys
from typing import Any, Tuple
from openai import AuthenticationError, OpenAI
import os
import argparse
import dotenv

_client = None

def get_client() -> Tuple[Any, str]:
    global _client

    try:
        api_key = os.getenv("OPENAI_API_KEY", "not-needed")
        api_url = os.getenv("OPENAI_BASE_URL", "")
        if api_url.strip() == "":
            api_url = None

        _client = OpenAI(base_url=api_url, api_key=api_key)
    except Exception as e:
        return None, f"Failed to create OpenAI client: {e}" 

    return _client, None

def list_patterns():
    pattern_path = os.path.dirname(os.path.realpath(__file__)) + "/patterns"
    if not os.path.exists(pattern_path):
        print("Patterns directory not found", file=sys.stderr)
        exit(1)

    for filename in os.listdir(pattern_path):
        print(filename)

def print_completion(completion, is_stream: bool):
    if is_stream:
        for chunk in completion:
            if chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)
    else:
        print(completion.choices[0].message.content)

def perform_pattern(pattern: str, is_stream: bool, temperature: float = 0.7, model: str = None):
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

    client, error = get_client()
    if error:
        print(error, file=sys.stderr)
        exit(1)

    # The model doesn't seem to matter at all
    if model is None:
        model = os.getenv("AI_MODEL", "gpt-4o")

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

        print_completion(completion, is_stream)
    except KeyboardInterrupt:
        print("User interrupted execution", file=sys.stderr)
        exit(2)
    except AuthenticationError as e:
        print("Failed to authenticate to server: " + e.body["message"], file=sys.stderr)
        exit(3)
    
    exit(0)

def main():
    dotenv.load_dotenv(os.path.dirname(os.path.realpath(__file__)) + "/.env")

    pattern = None
    temperature = 0.7
    model = None
    is_stream = sys.stdout.isatty()

    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--list-patterns", action='store_true', help="List available patterns")
    parser.add_argument("-t", "--temperature", type=float, help="The temperature to use")
    parser.add_argument("-m", "--model", type=str, help="The model to use")
    parser.add_argument("PATTERN", type=str, help="The pattern to use", nargs='?')

    args = parser.parse_args()

    if args.list_patterns:
        list_patterns()
        exit(0)

    if args.PATTERN is not None:
        pattern = args.PATTERN

    if args.temperature is not None:
        temperature = args.temperature

    if args.model is not None:
        model = args.model

    if pattern is None:
        parser.print_help()
        exit(0)

    perform_pattern(pattern, is_stream, temperature, model)

if __name__ == "__main__":
    main()