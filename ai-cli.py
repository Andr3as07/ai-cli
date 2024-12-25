#!/usr/bin/env python

import argparse
import dotenv
import os
import sys
import platform
from ai import build_history, list_patterns, load_pattern, perform_request

def switch_input():
    if not sys.stdin.isatty():
        if platform.system() == "Windows":
            sys.stdin = open("CON:", "r")
        else:
            sys.stdin.close()
            sys.stdin = os.fdopen(1)

def get_input(prompt: str = "") -> str:
    if prompt:
        print(prompt, end="", flush=True)
    return sys.stdin.read()

def print_completion(completion, is_stream: bool):
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

    return output

def main():
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
        patterns, error = list_patterns()
        if error is not None:
            print(error, file=sys.stderr)
            exit(1)
            return
        for pattern in patterns:
            print(pattern)
        exit(0)

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

    if not sys.stdin.isatty():
        user_input += sys.stdin.read()

    try:
        history = []
        if pattern is not None:
            # FIXME: This overrides the user defined system prompt
            system_input, user_input, error = load_pattern(pattern, user_input)
            if error is not None:
                print(error, file=sys.stderr)
                exit(1)
        elif system_input != "" or is_chat:
            pass # Nothing to do
        else:
            parser.print_help()
            exit(2)

        if system_input != "":
            build_history(history, system_input, user_input)
            
            completion, error = perform_request(history, is_stream, temperature, model)

            if error is not None:
                print(error, file=sys.stderr)
                exit(1)

            output = print_completion(completion, is_stream)
            history.append({"role": "assistant", "content": output})

        if is_chat:
            switch_input()
            while True:
                stdin = input("\n> ")

                history.append({"role": "user", "content": stdin})

                completion, error = perform_request(history, is_stream, temperature, model)
                if error is not None:
                    print(error, file=sys.stderr)
                    exit(1)

                output = print_completion(completion, is_stream)
                history.append({"role": "assistant", "content": output})
    except KeyboardInterrupt:
        print("User interrupted execution", file=sys.stderr)
        exit(3)

if __name__ == "__main__":
    main()