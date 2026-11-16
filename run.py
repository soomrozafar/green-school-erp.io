from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
from time import monotonic, sleep
from urllib.request import ProxyHandler, build_opener

from app import create_app
from config import ollama_address

app = create_app()
BUNDLED_MODEL = "qwen2.5:0.5b"


def running_models():
    try:
        with build_opener(ProxyHandler({})).open(f"http://{ollama_address()}/api/tags", timeout=0.6) as response:
            data = json.load(response)
        return {model["name"] for model in data["models"]}
    except (OSError, ValueError, KeyError, TypeError):
        return None


@contextmanager
def local_ollama():
    folder = Path(app.instance_path) / "ollama"
    executable = folder / "runtime" / "ollama.exe"
    model_index = folder / "models/manifests/registry.ollama.ai/library/qwen2.5/0.5b"
    if (
        os.name != "nt"
        or "SCHOOL_ERP_OLLAMA_MODEL" in os.environ
        or not executable.is_file()
        or not model_index.is_file()
    ):
        yield
        return

    process = None
    models = running_models()
    try:
        if models is None:
            environment = dict(os.environ, OLLAMA_HOST=ollama_address(),
                               OLLAMA_MODELS=str(folder / "models"), OLLAMA_NO_CLOUD="1")
            with (folder / "server.log").open("ab") as log:
                process = subprocess.Popen(
                    [str(executable), "serve"], cwd=folder, env=environment, stdout=log,
                    stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW,
                )
            deadline = monotonic() + 8
            while process.poll() is None and monotonic() < deadline:
                models = running_models()
                if models is not None:
                    break
                sleep(0.25)
        if models is not None and BUNDLED_MODEL in models:
            os.environ["SCHOOL_ERP_OLLAMA_MODEL"] = BUNDLED_MODEL
            print(f"ERP Assistant model: {BUNDLED_MODEL}")
        else:
            print("ERP Assistant: built-in mode. Check instance/ollama/server.log for details.")
    except OSError:
        app.logger.exception("Could not start the bundled Ollama runtime.")
    try:
        yield
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    with local_ollama():
        app.run(host="127.0.0.1", port=int(os.environ.get("SCHOOL_ERP_PORT", "5006")))
