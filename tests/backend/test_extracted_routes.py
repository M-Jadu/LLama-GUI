import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from backend.context import AppContext, AppPaths, ServerConfig
from backend.http import Request
from backend.routes import metrics, models, presets, status


class DummyResponse:
    def __init__(self):
        self.payload = None
        self.status = None
        self.text_payload = None

    def json(self, data, status=200):
        self.payload = data
        self.status = status

    def error(self, message, status=500, code=None, extra=None):
        self.payload = {"error": message, "status": status}
        if code:
            self.payload["code"] = code
        if extra:
            self.payload.update(extra)
        self.status = status

    def text(self, text, status=200, content_type="text/plain; charset=utf-8", headers=None):
        self.text_payload = text
        self.status = status


def make_context(root):
    root = Path(root)
    return AppContext(
        paths=AppPaths(
            root=root,
            llama=root / "llama",
            llama_bin=root / "llama" / "bin",
            llama_grammars=root / "llama" / "grammars",
            models=root / "models",
            presets=root / "presets",
            config_file=root / "config.json",
            ui=root / "ui",
            app_logo=root / "ui" / "assets" / "app-logo.png",
            tools=root / "tools",
            cloudflared=root / "tools" / "cloudflared",
        ),
        config=ServerConfig(llama_host="127.0.0.1", llama_port=8080),
    )


class ExtractedRouteTests(unittest.TestCase):
    def test_models_route_lists_only_gguf_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_context(tmp)
            ctx.paths.models.mkdir(parents=True)
            (ctx.paths.models / "model.gguf").write_bytes(b"x" * 1024)
            (ctx.paths.models / "notes.txt").write_text("ignore")
            response = DummyResponse()

            models.list_models(Request("GET", "/api/models", "", {}), response, ctx)

            self.assertEqual(response.payload, [{"name": "model.gguf", "size_mb": 0.0}])

    def test_presets_routes_list_save_and_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_context(tmp)
            response = DummyResponse()
            save_request = Request(
                "POST",
                "/api/presets",
                "",
                {},
                body={"name": "My/Preset", "data": {"temperature": 0.7}},
            )

            presets.save_preset(save_request, response, ctx)

            self.assertEqual(response.payload, {"saved": True, "name": "My_Preset"})
            self.assertTrue((ctx.paths.presets / "My_Preset.json").exists())

            list_response = DummyResponse()
            presets.list_presets(Request("GET", "/api/presets", "", {}), list_response, ctx)
            self.assertEqual(list_response.payload, [{"name": "My_Preset", "data": {"temperature": 0.7}}])

            delete_response = DummyResponse()
            delete_request = Request(
                "DELETE",
                "/api/presets/My_Preset",
                "",
                {},
                params={"name": "My_Preset"},
            )
            presets.delete_preset(delete_request, delete_response, ctx)
            self.assertEqual(delete_response.payload, {"deleted": True})
            self.assertFalse((ctx.paths.presets / "My_Preset.json").exists())

    def test_metrics_route_uses_context_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_context(tmp)
            calls = []

            def get_local_llama_metrics(host, port):
                calls.append((host, port))
                return "llama metrics", ""

            ctx.services["get_local_llama_metrics"] = get_local_llama_metrics
            response = DummyResponse()

            metrics.get_metrics(
                Request("GET", "/api/llama/metrics", "host=localhost&port=9090", {}),
                response,
                ctx,
            )

            self.assertEqual(calls, [("localhost", "9090")])
            self.assertEqual(response.text_payload, "llama metrics")

    def test_status_route_uses_context_services(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_context(tmp)
            cli_path = ctx.paths.llama_bin / "llama-cli.exe"
            cli_path.parent.mkdir(parents=True)
            cli_path.write_text("")
            ctx.services.update(
                {
                    "backend_specs": {"cpu": {"label": "CPU"}},
                    "binary_suffix": ".exe",
                    "current_arch": "x64",
                    "current_platform": "win32",
                    "find_tool_executable": lambda tool: ctx.paths.llama_bin / f"{tool}.exe",
                    "get_platform_label": lambda: "Windows",
                    "get_runtime_files": lambda: [SimpleNamespace(name="runtime.dll")],
                    "get_tool_filename": lambda tool: f"{tool}.exe",
                    "is_process_running": lambda: False,
                    "llama_tools": ["llama-cli"],
                    "load_config": lambda: {"tag": "b1", "backend": "cpu"},
                }
            )
            response = DummyResponse()

            status.get_status(Request("GET", "/api/status", "", {}), response, ctx)

            self.assertTrue(response.payload["installed"])
            self.assertEqual(response.payload["models_dir"], str(ctx.paths.models))
            self.assertEqual(response.payload["available_backends"], [{"id": "cpu", "label": "CPU"}])


if __name__ == "__main__":
    unittest.main()
