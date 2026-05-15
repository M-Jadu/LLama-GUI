import unittest

from backend.routing import Router


class RouterTests(unittest.TestCase):
    def test_exact_route_match(self):
        router = Router().add("GET", "/api/status", "handle_status")

        match = router.match("GET", "/api/status")

        self.assertIsNotNone(match)
        self.assertEqual(match.handler_name, "handle_status")
        self.assertEqual(match.params, {})

    def test_method_must_match(self):
        router = Router().add("GET", "/api/status", "handle_status")

        self.assertIsNone(router.match("POST", "/api/status"))

    def test_prefix_route_params(self):
        router = Router().add_prefix("DELETE", "/api/presets/", "delete_preset", "name")

        match = router.match("DELETE", "/api/presets/My%20Preset")

        self.assertIsNotNone(match)
        self.assertEqual(match.handler_name, "delete_preset")
        self.assertEqual(match.params, {"name": "My%20Preset"})

    def test_unknown_route(self):
        router = Router().add("GET", "/api/status", "handle_status")

        self.assertIsNone(router.match("GET", "/api/missing"))


if __name__ == "__main__":
    unittest.main()
