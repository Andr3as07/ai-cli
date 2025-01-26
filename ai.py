from typing import Any, Tuple
import os

_client = None


def get_client() -> Tuple[Any, str]:
    from openai import OpenAI
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


def get_user_patterns_path() -> str:
    user_patterns_path = None

    # TODO: Handle windows systems

    if os.getenv('XDG_CONFIG_HOME') is not None:
        user_patterns_path = os.getenv('XDG_CONFIG_HOME') + "/ai-cli/patterns"
    elif os.getenv('HOME'):
        user_patterns_path = os.getenv('HOME') + "/.config/ai-cli/patterns"

    return user_patterns_path


def get_builtin_patterns_path() -> str:
    return os.path.dirname(os.path.realpath(__file__)) + "/patterns"


def list_pattern_from_directory(path: str):
    if not os.path.exists(path):
        return []

    return os.listdir(path)


def find_pattern_path(pattern_name: str) -> str:
    user_patterns_path = get_user_patterns_path()

    if user_patterns_path is not None:
        patterns = list_pattern_from_directory(user_patterns_path)
        if pattern_name in patterns:
            return user_patterns_path + "/" + pattern_name

    builtin_patterns_path = get_builtin_patterns_path()

    if builtin_patterns_path is not None:
        patterns = list_pattern_from_directory(builtin_patterns_path)
        if pattern_name in patterns:
            return builtin_patterns_path + "/" + pattern_name

    return None


def list_patterns():
    patterns = []
    patterns += list_pattern_from_directory(get_builtin_patterns_path())

    user_patterns_path = get_user_patterns_path()
    if user_patterns_path is not None:
        patterns += list_pattern_from_directory(user_patterns_path)

    return patterns, None


def build_history(
        history: list,
        system_input: str,
        user_input: str = "",
        stdin: str = ""):
    history.append({"role": "system", "content": system_input})
    if user_input + stdin != "":
        history.append({"role": "user", "content": user_input + stdin})


def load_pattern(pattern: str, user_input: str = ""):
    pattern_path = find_pattern_path(pattern)
    if not os.path.exists(pattern_path):
        return None, None, f"Pattern '{pattern}' not found"

    if os.path.isfile(pattern_path + "/system.md"):
        with open(pattern_path + "/system.md") as f:
            system_input = f.read()

    if user_input == "" and os.path.isfile(pattern_path + "/user.md"):
        with open(pattern_path + "/user.md") as f:
            user_input = f.read()

    return system_input, user_input, None


def perform_request(
        history: list,
        is_stream: bool,
        temperature: float = 0.7,
        model: str = None):
    from openai import AuthenticationError, RateLimitError
    client, error = get_client()
    if error:
        return None, error

    if model is None:
        model = os.getenv("AI_MODEL", "gpt-4o")

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=history,
            temperature=temperature,
            stream=is_stream,
        )

        return completion, None
    except AuthenticationError as e:
        return None, "Failed to authenticate to server: " + e.body["message"]
    except RateLimitError as e:
        return None, "API rate limit exceeded: " + e.body["message"]


def extract_completion(completion, is_stream: bool):
    output = ""
    if is_stream:
        for chunk in completion:
            if chunk.choices[0].delta.content:
                data = chunk.choices[0].delta.content
                output += data
    else:
        output = completion.choices[0].message.content

    return output
