"""Local llama-server metrics proxy route."""

import urllib.parse

from backend.services import process_manager


def _get_metrics_target(ctx, query):
    runtime = process_manager.get_active_runtime_snapshot(ctx)
    if runtime and runtime.get("tool") == "llama-server":
        return runtime.get("host"), runtime.get("port")
    return (
        (query.get("host") or [ctx.config.llama_host])[0],
        (query.get("port") or [str(ctx.config.llama_port)])[0],
    )


def get_metrics(request, response, ctx):
    query = urllib.parse.parse_qs(request.query)
    host, port = _get_metrics_target(ctx, query)
    metrics_text, error = ctx.services.get_local_llama_metrics(
        host,
        port,
        process_manager.get_active_llama_authorization(
            ctx,
            request.headers.get("Authorization", ""),
        ),
    )
    if metrics_text is None:
        response.error(error, 502)
        return
    response.text(metrics_text)


def get_slots(request, response, ctx):
    query = urllib.parse.parse_qs(request.query)
    host, port = _get_metrics_target(ctx, query)
    slots_text, error = ctx.services.get_local_llama_slots(
        host,
        port,
        process_manager.get_active_llama_authorization(
            ctx,
            request.headers.get("Authorization", ""),
        ),
    )
    if slots_text is None:
        response.error(error, 502)
        return
    response.text(slots_text, content_type="application/json; charset=utf-8")
