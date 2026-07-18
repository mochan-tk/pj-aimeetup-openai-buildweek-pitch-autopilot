import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from generate import DEFAULT_API_VERSION, SLIDE_IDS, generate


FIXTURE = Path(__file__).parent / "fixtures" / "context_sample.json"


def valid_deck(langs=("ja", "en")):
    requested = set(langs)
    return {
        "title": "Pitch Autopilot",
        "slides": [
            {
                "id": slide_id,
                "heading_ja": "見出し" if "ja" in requested else "",
                "heading_en": "Heading" if "en" in requested else "",
                "bullets_ja": ["事実"] if "ja" in requested else [],
                "bullets_en": ["Fact"] if "en" in requested else [],
                "image": None,
                "arch_text": "repo -> context -> deck" if slide_id == "demo" else None,
            }
            for slide_id in SLIDE_IDS
        ],
        "script_ja": "事実に基づく説明です。" if "ja" in requested else "",
        "script_en": "A short fact grounded pitch." if "en" in requested else "",
    }


class FakeCompletions:
    def __init__(self, payloads):
        self.payloads = iter(payloads)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = next(self.payloads)
        output = payload if isinstance(payload, str) else json.dumps(payload)
        message = SimpleNamespace(content=output)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def fake_client(payloads):
    return SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions(payloads)))


class GenerateTests(unittest.TestCase):
    def setUp(self):
        self.context = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_happy_path_uses_strict_structured_outputs(self):
        client = fake_client([valid_deck()])
        result = generate(
            self.context, ["ja", "en"], client, deployment="pitch-deployment"
        )

        self.assertEqual([slide["id"] for slide in result["slides"]], list(SLIDE_IDS))
        self.assertEqual(len(client.chat.completions.calls), 1)
        call = client.chat.completions.calls[0]
        self.assertEqual(call["model"], "pitch-deployment")
        self.assertEqual(call["temperature"], 0)
        self.assertEqual(call["response_format"]["type"], "json_schema")
        self.assertTrue(call["response_format"]["json_schema"]["strict"])

    def test_schema_invalid_response_retries_once_then_raises(self):
        client = fake_client([{"title": "invalid"}, "not json"])
        with self.assertRaisesRegex(ValueError, "after 2 attempts"):
            generate(
                self.context, ["ja", "en"], client, deployment="pitch-deployment"
            )
        self.assertEqual(len(client.chat.completions.calls), 2)

    def test_misplaced_demo_fallback_is_retried(self):
        invalid = valid_deck()
        invalid["slides"][3]["arch_text"] = None
        invalid["slides"][4]["arch_text"] = "misplaced fallback"
        client = fake_client([invalid, valid_deck()])

        result = generate(
            self.context, ["ja", "en"], client, deployment="pitch-deployment"
        )

        self.assertEqual(len(client.chat.completions.calls), 2)
        self.assertEqual(result["slides"][3]["arch_text"], "repo -> context -> deck")

    def test_unrequested_language_is_empty(self):
        client = fake_client([valid_deck(("ja",))])
        result = generate(self.context, ["ja"], client, deployment="pitch-deployment")

        self.assertTrue(all(slide["heading_en"] == "" for slide in result["slides"]))
        self.assertTrue(all(slide["bullets_en"] == [] for slide in result["slides"]))
        self.assertEqual(result["script_en"], "")

    def test_default_client_uses_azure_configuration_and_deployment(self):
        created = []
        client = fake_client([valid_deck()])

        def azure_openai(**kwargs):
            created.append(kwargs)
            return client

        environment = {
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com/",
            "AZURE_OPENAI_API_KEY": "test-secret",
            "AZURE_OPENAI_DEPLOYMENT": "pitch-deployment",
        }
        with patch.dict(os.environ, environment, clear=True), patch.dict(
            sys.modules, {"openai": SimpleNamespace(AzureOpenAI=azure_openai)}
        ):
            generate(self.context, ["ja", "en"])

        self.assertEqual(
            created,
            [{
                "azure_endpoint": environment["AZURE_OPENAI_ENDPOINT"],
                "api_key": environment["AZURE_OPENAI_API_KEY"],
                "api_version": DEFAULT_API_VERSION,
            }],
        )
        self.assertEqual(client.chat.completions.calls[0]["model"], "pitch-deployment")

    def test_missing_azure_configuration_names_variables_without_values(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                RuntimeError,
                "AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT",
            ):
                generate(self.context, ["ja", "en"])


if __name__ == "__main__":
    unittest.main()
