from pathlib import Path

def build_index(data_dir: Path = Path('data/knowledge')) -> None:
    """Stub for building a local knowledge index."""
    data_dir.mkdir(parents=True, exist_ok=True)
    # Real implementation would scan PDFs/MD and build a LlamaIndex here.
