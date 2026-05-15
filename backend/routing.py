"""Small route registry used by the stdlib HTTP entrypoint."""

from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Tuple


@dataclass(frozen=True)
class RouteMatch:
    handler_name: str
    params: Mapping[str, str]


@dataclass(frozen=True)
class _Route:
    method: str
    path: str
    handler_name: str
    param_name: Optional[str] = None
    is_prefix: bool = False


class Router:
    def __init__(self) -> None:
        self._exact: Dict[Tuple[str, str], RouteMatch] = {}
        self._prefixes = []

    def add(self, method: str, path: str, handler_name: str) -> "Router":
        self._exact[(method.upper(), path)] = RouteMatch(handler_name, {})
        return self

    def add_prefix(
        self,
        method: str,
        prefix: str,
        handler_name: str,
        param_name: Optional[str] = None,
    ) -> "Router":
        self._prefixes.append(
            _Route(
                method=method.upper(),
                path=prefix,
                handler_name=handler_name,
                param_name=param_name,
                is_prefix=True,
            )
        )
        return self

    def match(self, method: str, path: str) -> Optional[RouteMatch]:
        method = method.upper()
        exact = self._exact.get((method, path))
        if exact:
            return exact

        for route in self._prefixes:
            if route.method != method or not path.startswith(route.path):
                continue
            params = {}
            if route.param_name:
                params[route.param_name] = path[len(route.path) :]
            return RouteMatch(route.handler_name, params)
        return None
