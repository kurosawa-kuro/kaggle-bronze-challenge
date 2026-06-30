"""Vertex AI 推論コンテナ（LightGBM seed-bag）。Batch Prediction / Endpoint 用。

`runner.experiment.train` が保存した `model/`（`booster_NNN.txt` + `manifest.json`）を読み、
全 booster の平均を返す（`pipelines.score.predict` と同じ推論）。

Vertex のカスタムコンテナ契約に従う:
- `AIP_HEALTH_ROUTE`（既定 /health）GET → 200
- `AIP_PREDICT_ROUTE`（既定 /predict）POST `{"instances": [[...], ...]}` → `{"predictions": [...]}`
- `AIP_HTTP_PORT`（既定 8080）で listen
- モデルは `AIP_STORAGE_URI`（gs://...）を起動時に DL。ローカル検証は `MODEL_DIR` で差し替え。

新しい infra lib を足さないため HTTP は stdlib のみ（Flask 等は使わない）。
"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import lightgbm as lgb
import numpy as np

HEALTH_ROUTE = os.environ.get("AIP_HEALTH_ROUTE", "/health")
PREDICT_ROUTE = os.environ.get("AIP_PREDICT_ROUTE", "/predict")
PORT = int(os.environ.get("AIP_HTTP_PORT", "8080"))


def _resolve_model_dir() -> str:
    """ローカル/テストは MODEL_DIR、Vertex は AIP_STORAGE_URI(gs://) を DL。"""
    local = os.environ.get("MODEL_DIR")
    if local:
        return local
    uri = os.environ.get("AIP_STORAGE_URI", "")
    if uri.startswith("gs://"):
        return _download(uri)
    return "model"


def _download(gs_uri: str) -> str:
    from google.cloud import storage

    dest = "/tmp/model"
    os.makedirs(dest, exist_ok=True)
    _, _, rest = gs_uri.partition("gs://")
    bucket_name, _, prefix = rest.partition("/")
    client = storage.Client()
    for blob in client.list_blobs(bucket_name, prefix=prefix.rstrip("/") + "/"):
        name = blob.name.rsplit("/", 1)[-1]
        if name:
            blob.download_to_filename(os.path.join(dest, name))
    return dest


class Predictor:
    def __init__(self, model_dir: str) -> None:
        with open(os.path.join(model_dir, "manifest.json"), encoding="utf-8") as fp:
            manifest = json.load(fp)
        self.boosters = [
            lgb.Booster(model_file=os.path.join(model_dir, b)) for b in manifest["boosters"]
        ]
        self.num_class = int(manifest.get("num_class", 1))
        if not self.boosters:
            raise RuntimeError(f"no boosters found in {model_dir}")

    def predict(self, instances: list) -> list:
        X = np.asarray(instances, dtype=float)
        preds = np.mean([b.predict(X) for b in self.boosters], axis=0)
        return preds.tolist()


_PREDICTOR: Predictor | None = None


def _predictor() -> Predictor:
    global _PREDICTOR
    if _PREDICTOR is None:
        _PREDICTOR = Predictor(_resolve_model_dir())
    return _PREDICTOR


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        if self.path == HEALTH_ROUTE:
            self._send(200, {"status": "ok"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != PREDICT_ROUTE:
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            predictions = _predictor().predict(payload["instances"])
            self._send(200, {"predictions": predictions})
        except Exception as exc:  # noqa: BLE001 - 予測失敗は 500 で返す
            self._send(500, {"error": str(exc)})

    def log_message(self, *args) -> None:  # アクセスログ抑制
        pass


def main() -> None:
    _predictor()  # 起動時にロード（失敗を即顕在化）
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[serving] listening :{PORT}  health={HEALTH_ROUTE} predict={PREDICT_ROUTE}")
    server.serve_forever()


if __name__ == "__main__":
    main()
