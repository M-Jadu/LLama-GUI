"""Model file API routes."""

from backend.services.model_scanner import create_scanner


# Create scanner instance
_scanner = None


def _get_scanner(ctx):
    """Get or create scanner instance."""
    global _scanner
    if _scanner is None:
        _scanner = create_scanner(ctx.paths.root, cache_ttl_seconds=300)
    return _scanner


def list_models(request, response, ctx):
    """List all GGUF model files from scan paths."""
    scanner = _get_scanner(ctx)
    models = scanner.scan()
    
    # Transform to match frontend expectations (name + size_mb)
    # Models from scanner have: name, path, size_mb
    # But also include local models/ directory for backward compatibility
    result = []
    seen_names = set()
    
    # First add scanned models from all paths
    for model in models:
        if model.get("name"):
            result.append({
                "name": model["name"],
                "size_mb": model.get("size_mb", 0),
                "path": model.get("path", ""),
            })
            seen_names.add(model["name"])
    
    # Then add local models/ directory files (for backward compatibility)
    models_dir = ctx.paths.models
    if models_dir.exists():
        try:
            for path in sorted(models_dir.iterdir()):
                if path.is_file() and path.suffix.lower() == ".gguf":
                    name = path.name
                    if name not in seen_names:
                        size_mb = path.stat().st_size / (1024 * 1024)
                        result.append({
                            "name": name,
                            "size_mb": round(size_mb, 2),
                            "path": str(path),
                        })
                        seen_names.add(name)
        except (OSError, IOError):
            pass  # Ignore errors reading models dir
    
    response.json(result)


def rescan_models(request, response, ctx):
    """Force rescan of model directories (invalidate cache)."""
    scanner = _get_scanner(ctx)
    models = scanner.rescan()
    
    # Transform result
    result = []
    seen_names = set()
    
    for model in models:
        if model.get("name"):
            result.append({
                "name": model["name"],
                "size_mb": model.get("size_mb", 0),
                "path": model.get("path", ""),
            })
            seen_names.add(model["name"])
    
    # Add local models/ directory files
    models_dir = ctx.paths.models
    if models_dir.exists():
        try:
            for path in sorted(models_dir.iterdir()):
                if path.is_file() and path.suffix.lower() == ".gguf":
                    name = path.name
                    if name not in seen_names:
                        size_mb = path.stat().st_size / (1024 * 1024)
                        result.append({
                            "name": name,
                            "size_mb": round(size_mb, 2),
                            "path": str(path),
                        })
                        seen_names.add(name)
        except (OSError, IOError):
            pass
    
    response.json(result)
