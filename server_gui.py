from pathlib import Path


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    script = root / "scripts" / "server_gui.py"
    globals_dict = {
        "__name__": "__main__",
        "__file__": str(Path(__file__).resolve()),
        "__package__": None,
        "__cached__": None,
    }
    exec(compile(script.read_text(encoding="utf-8"), str(script), "exec"), globals_dict)
