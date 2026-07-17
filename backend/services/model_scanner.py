"""Model discovery and scanning service for GGUF files."""

import json
import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple


class ModelScannerCache:
    """Thread-safe cache for model scan results."""
    
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self.lock = threading.Lock()
        self.data: Dict[str, object] = {}
        self.timestamp: float = 0
    
    def is_valid(self) -> bool:
        """Check if cache is still valid."""
        if not self.data:
            return False
        elapsed = time.time() - self.timestamp
        return elapsed < self.ttl_seconds
    
    def get(self) -> Optional[Dict[str, object]]:
        """Get cached data if valid."""
        with self.lock:
            if self.is_valid():
                return self.data.copy()
        return None
    
    def set(self, data: Dict[str, object]) -> None:
        """Set cache data."""
        with self.lock:
            self.data = data.copy()
            self.timestamp = time.time()
    
    def invalidate(self) -> None:
        """Invalidate cache."""
        with self.lock:
            self.data = {}
            self.timestamp = 0


class ModelScanner:
    """Scans multiple directories for GGUF model files."""
    
    def __init__(self, config_file: Optional[Path] = None, cache_ttl_seconds: int = 300):
        """
        Initialize scanner.
        
        Args:
            config_file: Path to scanner-config.json for additional scan paths.
            cache_ttl_seconds: Cache TTL for scan results.
        """
        self.config_file = config_file
        self.cache = ModelScannerCache(ttl_seconds=cache_ttl_seconds)
        self.scan_lock = threading.Lock()
    
    def get_default_scan_paths(self) -> List[Path]:
        """Get default scan paths from environment variables."""
        paths: List[Path] = []
        
        # HuggingFace cache path
        hf_cache = os.environ.get("HUGGINGFACE_HUB_CACHE")
        if hf_cache:
            paths.append(Path(hf_cache))
        else:
            hf_home = os.environ.get("HF_HOME")
            if hf_home:
                paths.append(Path(hf_home) / "hub")
        
        # LM Studio models path
        lm_studio = os.environ.get("LMSTUDIO_MODELS_DIR")
        if lm_studio:
            paths.append(Path(lm_studio))
        
        return [p for p in paths if p and p.is_dir()]
    
    def get_config_scan_paths(self) -> List[Path]:
        """Read additional scan paths from config file."""
        if not self.config_file or not self.config_file.exists():
            return []
        
        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError, IOError):
            return []
        
        # Handle both array and comma-separated string formats
        scan_paths = config.get("scan_paths", [])
        if isinstance(scan_paths, str):
            # Comma-separated string
            paths = [p.strip() for p in scan_paths.split(",") if p.strip()]
        elif isinstance(scan_paths, list):
            # Array format
            paths = [str(p) for p in scan_paths if p]
        else:
            paths = []
        
        # Convert to Path objects and filter valid dirs
        result = []
        for path_str in paths:
            path = Path(path_str).expanduser().resolve()
            if path.is_dir():
                result.append(path)
        
        return result
    
    def get_all_scan_paths(self) -> List[Path]:
        """Get all scan paths (default + config)."""
        paths = self.get_default_scan_paths()
        paths.extend(self.get_config_scan_paths())
        
        # Deduplicate while preserving order
        seen = set()
        unique_paths = []
        for p in paths:
            resolved = str(p.resolve())
            if resolved not in seen:
                seen.add(resolved)
                unique_paths.append(p)
        
        return unique_paths
    
    def scan_directory(self, directory: Path) -> List[Dict[str, object]]:
        """
        Recursively scan directory for .gguf files.
        
        Args:
            directory: Directory to scan.
        
        Returns:
            List of model dicts with name, path, size_mb.
        """
        models: List[Dict[str, object]] = []
        
        if not directory.is_dir():
            return models
        
        try:
            # Use rglob for recursive globbing
            for gguf_file in directory.rglob("*.gguf"):
                if gguf_file.is_file():
                    try:
                        size_mb = gguf_file.stat().st_size / (1024 * 1024)
                        models.append({
                            "name": gguf_file.name,
                            "path": str(gguf_file),
                            "size_mb": round(size_mb, 2),
                        })
                    except (OSError, IOError):
                        # Skip files we can't stat
                        pass
        except (OSError, IOError):
            # Skip directories we can't read
            pass
        
        return models
    
    def scan(self) -> List[Dict[str, object]]:
        """
        Scan all configured paths for GGUF files.
        
        Returns:
            List of model dicts, deduplicated by file path.
        """
        # Check cache first
        cached = self.cache.get()
        if cached is not None:
            return cached.get("models", [])
        
        # Acquire lock for scanning
        with self.scan_lock:
            # Double-check cache after acquiring lock
            cached = self.cache.get()
            if cached is not None:
                return cached.get("models", [])
            
            # Perform scan
            all_models: List[Dict[str, object]] = []
            seen_paths: set = set()
            
            for directory in self.get_all_scan_paths():
                dir_models = self.scan_directory(directory)
                for model in dir_models:
                    path_str = model.get("path", "")
                    if path_str and path_str not in seen_paths:
                        seen_paths.add(path_str)
                        all_models.append(model)
            
            # Sort by name for consistent ordering
            all_models.sort(key=lambda m: str(m.get("name", "")))
            
            # Cache results
            result = {"models": all_models, "scanned_at": time.time()}
            self.cache.set(result)
            
            return all_models
    
    def rescan(self) -> List[Dict[str, object]]:
        """Force rescan, invalidating cache."""
        self.cache.invalidate()
        return self.scan()
    
    def create_default_config(self) -> None:
        """Create a default scanner config file with instructions."""
        if not self.config_file:
            return
        
        if self.config_file.exists():
            return  # Don't overwrite existing config
        
        default_config = {
            "scan_paths": [
                "# Additional paths to scan for GGUF models.",
                "# Can be an array or comma-separated string.",
                "# Examples:",
                "# - /home/user/models",
                "# - C:\\\\Users\\\\user\\\\Downloads",
                "# Paths can use ~ for home directory.",
                "~/.cache/lm-studio/models",
            ]
        }
        
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w") as f:
                json.dump(default_config, f, indent=2)
        except (OSError, IOError):
            pass  # Silent failure on write


def create_scanner(root_dir: Path, cache_ttl_seconds: int = 300) -> ModelScanner:
    """
    Factory function to create a ModelScanner instance.
    
    Args:
        root_dir: Root directory of the app (usually ROOT_DIR from config).
        cache_ttl_seconds: Cache TTL for scan results.
    
    Returns:
        Configured ModelScanner instance.
    """
    config_file = root_dir / "scanner-config.json"
    scanner = ModelScanner(config_file=config_file, cache_ttl_seconds=cache_ttl_seconds)
    scanner.create_default_config()
    return scanner
