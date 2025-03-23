import json
import os
from typing import Any
from typing import Optional

from driver_openai import OpenAIDriver

providers = {}
completion_models = {}


class Provider:
    def __init__(self, driver_name, base_address, token):
        self.driver_name = driver_name
        self.base_address = base_address
        self.token = token

    def get_driver(self) -> (Any, str):
        if self.driver_name == "openai":
            return OpenAIDriver(self.base_address, self.token), None
        return None, "Unknown driver " + self.driver_name


class CompletionModel:
    def __init__(self, model_name: str, provider_name: str):
        self.model_name = model_name
        self.provider_name = provider_name


def reset():
    global providers
    global completion_models

    providers = {}
    completion_models = {}


def load_models_file(path: str):
    global providers
    global completion_models

    with open(path, "r") as f:
        data = json.load(f)

    for provider_name, provider_data in data["providers"].items():
        providers[provider_name] = Provider(
            provider_data["driver"],
            provider_data["base_address"],
            os.getenv(provider_data["token"]) or provider_data["token"],
        )

    for model_name, model_data in data["completion"].items():
        completion_models[model_name] = CompletionModel(
            model_data["model_name"],
            model_data["provider"],
        )


def get_completion_model_and_provider(name: str) -> (
    Optional[CompletionModel],
    Optional[Provider],
    str,
):
    if name not in completion_models:
        return None, None, "Invalid model " + str(name)

    model = completion_models[name]

    if model.provider_name not in providers:
        return None, None, "Invalid provider " + model.provider_name

    provider = providers[model.provider_name]

    return model, provider, None
