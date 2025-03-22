#!/usr/bin/env python
import argparse
import json
import os
import sys
import time
from enum import auto
from enum import Enum

import ai

enable_color = False
output_buffer = []


class OutputType(Enum):
    User = auto()
    Assistant = auto()
    System = auto()
    Info = auto()
    Error = auto()


def get_cache_dir() -> str:
    # TODO: Handle windows systems
    if os.getenv("XDG_CACHE_HOME") is not None:
        return os.getenv("XDG_CACHE_HOME") + "/ai-cli"
    elif os.getenv("HOME") is not None:
        return os.getenv("HOME") + "/.cache/ai-cli"
    return None


def save_session(filename: str):
    dir = get_cache_dir()
    if dir is None:
        return

    os.makedirs(dir, exist_ok=True)

    with open(dir + "/" + filename, "w") as f:
        json.dump(output_buffer, f)


def append_to_session(type: OutputType, content: str):
    global output_buffer

    if len(content) == 0:
        return

    if len(output_buffer) > 0 and output_buffer[-1]["type"] == type.name:
        output_buffer[-1]["content"] += content
    else:
        output_buffer.append(
            {
                "type": type.name,
                "content": content,
            },
        )


def output(type: OutputType, content, *, end="\n", flush: bool = False):
    map = {
        OutputType.User: (sys.stdout, True, True, ""),
        OutputType.Assistant: (sys.stdout, True, True, "\033[36m"),
        OutputType.System: (sys.stdout, False, True, "\033[32m"),
        OutputType.Info: (sys.stdout, True, False, ""),
        OutputType.Error: (sys.stderr, True, False, "\033[31m"),
    }

    (file, write_out, append, color) = map[type]

    if append:
        append_to_session(type, str(content))

    if write_out:
        if enable_color:
            content = color + str(content) + "\033[0m"
        print(content, file=file, end=end, flush=flush)


def switch_input():
    import platform

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
    result = ""
    if is_stream:
        for chunk in completion:
            if chunk.choices[0].delta.content:
                data = chunk.choices[0].delta.content
                output(OutputType.Assistant, data, end="", flush=True)
                result += data
    else:
        result = completion.choices[0].message.content
        output(OutputType.Assistant, result)

    return result


def list_patterns():
    patterns, error = ai.list_patterns()
    if error is not None:
        output(OutputType.Error, error)
        exit(1)
        return
    for pattern in patterns:
        output(OutputType.Info, pattern)


def perform(
    patterns: list[str],
    user_input: str,
    system_input: str,
    is_chat: bool,
    is_stream: bool,
    model: str,
    temperature: float,
):
    history = []

    # FIXME: We assume that we have at least one pattern.
    # The System sould still work if we use a user suppied system prompt.

    output(OutputType.Info, "Applying pattern: " + patterns[0])
    system_input, user_input, error = ai.load_pattern(
        patterns[0],
        system_input,
        user_input,
    )

    if error is not None:
        output(OutputType.Error, error)
        exit(1)

    if system_input != "":
        append_to_session(OutputType.System, system_input)
        if user_input is not None:
            append_to_session(OutputType.User, user_input)
        ai.build_history(history, system_input, user_input)

        completion, error = ai.perform_request(
            history,
            is_stream,
            temperature,
            model,
        )

        if error is not None:
            output(OutputType.Error, error)
            exit(1)

        result = print_completion(completion, is_stream)
        history.append({"role": "assistant", "content": result})

        for pattern in patterns[1:]:
            output(OutputType.Info, "\nApplying pattern: " + pattern)
            system_input, user_input, error = ai.load_pattern(
                pattern,
                user_input=result,
            )
            if error is not None:
                output(OutputType.Error, error)
                exit(1)
            if system_input == "":
                output(
                    OutputType.Error,
                    "System input required for subsequent patterns",
                )
                exit(1)
            append_to_session(OutputType.System, system_input)
            if user_input is not None:
                append_to_session(OutputType.User, user_input)
            ai.build_history(history, system_input, user_input)

            completion, error = ai.perform_request(
                history,
                is_stream,
                temperature,
                model,
            )

            if error is not None:
                output(OutputType.Error, error)
                exit(1)

            result = print_completion(completion, is_stream)
            history.append({"role": "assistant", "content": result})

    if is_chat:
        output(OutputType.Info, "\nStarting Chat session")
        switch_input()
        while True:
            stdin = input("\n> ")

            history.append({"role": "user", "content": stdin})
            append_to_session(OutputType.User, stdin)

            completion, error = ai.perform_request(
                history,
                is_stream,
                temperature,
                model,
            )
            if error is not None:
                output(OutputType.Error, error)
                exit(1)

            result = print_completion(completion, is_stream)
            history.append({"role": "assistant", "content": result})


def load_environment():
    import dotenv

    dotenv.load_dotenv(os.path.dirname(os.path.realpath(__file__)) + "/.env")


def generate_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-l",
        "--list-patterns",
        action="store_true",
        help="List available patterns",
    )
    parser.add_argument(
        "-t",
        "--temperature",
        type=float,
        help="The temperature to use",
    )
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        help="The model to use",
    )
    parser.add_argument(
        "-p",
        "--prompt",
        type=str,
        help="Define a custom system prompt",
    )
    parser.add_argument(
        "-u",
        "--user",
        type=str,
        help="Define a custom user input",
    )
    parser.add_argument(
        "-c",
        "--chat",
        action="store_true",
        help="Enter chat mode",
    )
    parser.add_argument(
        "PATTERN",
        type=str,
        help="The pattern to use",
        nargs="*",
    )

    return parser


def get_optional_argument(args: argparse.Namespace, name, defval=None):
    value = args.__getattribute__(name)
    if value is None:
        return defval
    return value


def main():
    global enable_color

    timestamp = time.gmtime()
    pattern = None
    temperature = 0.7
    model = None
    is_stream = sys.stdout.isatty()
    system_input = ""
    user_input = ""
    is_chat = False

    should_save_session = is_stream or is_chat

    enable_color = is_stream

    parser = generate_parser()
    args = parser.parse_args()

    if args.list_patterns:
        list_patterns()
        exit(0)

    patterns = get_optional_argument(args, "PATTERN")
    temperature = get_optional_argument(args, "temperature", temperature)
    model = get_optional_argument(args, "model")
    system_input = get_optional_argument(args, "prompt")
    user_input = get_optional_argument(args, "user", "")
    is_chat = get_optional_argument(args, "chat", is_chat)

    if len(patterns) == 0 and system_input is None and not is_chat:
        parser.print_help()
        exit(2)

    if not sys.stdin.isatty():
        user_input += sys.stdin.read()

    load_environment()

    try:
        if patterns is not None:
            perform(
                patterns,
                user_input,
                system_input,
                is_chat,
                is_stream,
                model,
                temperature,
            )
    except KeyboardInterrupt:
        output(OutputType.Error, "User interrupted execution")

    if should_save_session:
        now = time.strftime("%Y%m%d%H%M%S", timestamp)
        pattern_text = "nopttern"
        if len(patterns) > 1:
            pattern_text = "multiplepatterns"
        else:
            pattern_text = patterns[0]
        filename = f"{now}_{pattern_text}.json"
        save_session(filename)


if __name__ == "__main__":
    main()
