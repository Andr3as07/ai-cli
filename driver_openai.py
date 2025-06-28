from typing import Any
from typing import Optional
from typing import Tuple

from openai import NotFoundError


class OpenAIDriver:
    def __init__(self, base_address, token):
        self.base_address = base_address
        self.token = token
        self._client = None

    def get_client(self) -> Tuple[Any, Optional[str]]:
        from openai import OpenAI

        global _client

        try:
            self._client = OpenAI(
                base_url=self.base_address,
                api_key=self.token,
            )
        except Exception as e:
            return None, f"Failed to create OpenAI client: {e}"

        return self._client, None

    def perform_request(
        self,
        history: list,
        is_stream: bool,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ):
        from openai import AuthenticationError, RateLimitError

        client, error = self.get_client()
        if error:
            return None, error

        if model is None:
            return None, "No model defined"

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
        except NotFoundError as e:
            return None, "Not found: " + e.body["message"]
