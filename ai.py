#! /usr/bin/python

import platform
import sys
from typing import Any, Tuple
from openai import AuthenticationError, OpenAI
import os
import argparse
import dotenv

_client = None
history = None

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

def switch_input():
    if not sys.stdin.isatty():
        if platform.system() == "Windows":
            sys.stdin = open("CON:", "r")
        else:
            # TODO: Unix, UNTESTED
            sys.stdin.close()
            sys.stdin = os.fdopen(1)

def get_input(prompt: str = "") -> str:
    if prompt:
        print(prompt, end="", flush=True)
    return sys.stdin.read()

def list_patterns():
    pattern_path = os.path.dirname(os.path.realpath(__file__)) + "/patterns"
    if not os.path.exists(pattern_path):
        print("Patterns directory not found", file=sys.stderr)
        exit(1)

    for filename in os.listdir(pattern_path):
        print(filename)

def print_completion(completion, is_stream: bool):
    global history

    output = ""
    if is_stream:
        for chunk in completion:
            if chunk.choices[0].delta.content:
                data = chunk.choices[0].delta.content
                print(data, end="", flush=True)
                output += data
    else:
        output = completion.choices[0].message.content
        print(output)

    history.append({"role": "assistant", "content": output})

def perform_chat(is_stream: bool, temperature: float = 0.7, model: str = None):
    global history

    stdin = input("\n> ")
    
    client, error = get_client()
    if error:
        print(error, file=sys.stderr)
        exit(1)

    history.append({"role": "user", "content": stdin})

    if model is None:
        model = os.getenv("AI_MODEL", "gpt-4o")

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=history,
            temperature=temperature,
            stream=is_stream,
        )

        print_completion(completion, is_stream)
    except AuthenticationError as e:
        print("Failed to authenticate to server: " + e.body["message"], file=sys.stderr)
        exit(4)

def perform_request(system_input: str, user_input: str, is_stream: bool, temperature: float = 0.7, model: str = None):
    global history

    stdin = get_input()

    client, error = get_client()
    if error:
        print(error, file=sys.stderr)
        exit(1)

    if model is None:
        model = os.getenv("AI_MODEL", "gpt-4o")

    if history is None:
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
    except AuthenticationError as e:
        print("Failed to authenticate to server: " + e.body["message"], file=sys.stderr)
        exit(4)

def perform_pattern(pattern: str, is_stream: bool, temperature: float = 0.7, model: str = None, user_input: str = ""):
    pattern_path = os.path.dirname(os.path.realpath(__file__)) + "/patterns/" + pattern
    if not os.path.exists(pattern_path):
        print(f"Pattern '{pattern}' not found", file=sys.stderr)
        exit(1)

    system_input = ""

    if os.path.isfile(pattern_path + "/system.md"):
        with open(pattern_path + "/system.md") as f:
            system_input = f.read()

    if system_input == "":
        print("No system input provided", file=sys.stderr)
        exit(1)

    if user_input == "" and os.path.isfile(pattern_path + "/user.md"):
        with open(pattern_path + "/user.md") as f:
            user_input = f.read()

    perform_request(system_input, user_input, is_stream, temperature, model)

def main():
    global history

    dotenv.load_dotenv(os.path.dirname(os.path.realpath(__file__)) + "/.env")

    pattern = None
    temperature = 0.7
    model = None
    is_stream = sys.stdout.isatty()
    system_input = ""
    user_input = ""
    is_chat = False

    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--list-patterns", action='store_true', help="List available patterns")
    parser.add_argument("-t", "--temperature", type=float, help="The temperature to use")
    parser.add_argument("-m", "--model", type=str, help="The model to use")
    parser.add_argument("-p", "--prompt", type=str, help="Define a custom system prompt")
    parser.add_argument("-u", "--user", type=str, help="Define a custom user input")
    parser.add_argument("-c", "--chat", action='store_true', help="Enter chat mode after creating the initial output")
    parser.add_argument("PATTERN", type=str, help="The pattern to use", nargs='?')

    args = parser.parse_args()

    if args.list_patterns:
        list_patterns()
        exit(2)

    if args.PATTERN is not None:
        pattern = args.PATTERN

    if args.temperature is not None:
        temperature = args.temperature

    if args.model is not None:
        model = args.model

    if args.prompt is not None:
        system_input = args.prompt

    if args.user is not None:
        user_input = args.user
    
    if args.chat is not None:
        is_chat = args.chat

    if pattern is None and system_input == "" and not is_chat:
        parser.print_help()
        exit(2)

    try:
        if pattern is not None:
            perform_pattern(pattern, is_stream, temperature, model, user_input)
        elif system_input != "":
            perform_request(system_input, user_input, is_stream, temperature, model)
        elif is_chat:
            pass # Nothing to do
        else:
            parser.print_help()
            exit(2)

        if history is None:
            history = []
            
            if system_input != "":
                history.append({"role": "system", "content": system_input})
            
            if user_input != "":
                history.append({"role": "user", "content": user_input})
            if not sys.stdin.isatty():
                data = sys.stdin.read()
                if data != "":
                    history.append({"role": "user", "content": data})

        if is_chat:
            switch_input()
            while True:
                perform_chat(is_stream, temperature, model)
    except KeyboardInterrupt:
        print("User interrupted execution", file=sys.stderr)
        exit(3)

if __name__ == "__main__":
    main()