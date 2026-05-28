"""Export the concierge classifier to ONNX format.

Owner C (Rayan) owns the model artifact and this export script.

Usage:
    python apps/modelserver/scripts/export_onnx.py \
        --model-card apps/modelserver/artifacts/model/model_card.json \
        --output apps/modelserver/artifacts/model/concierge_classifier.onnx

Requirements:
    pip install skl2onnx onnxruntime

After export:
    1. Compute the SHA-256 of the output file.
    2. Update model_card.json:
         "artifact": {
             "path": "concierge_classifier.onnx",
             "sha256": "<new hash>",
             "format": "onnx",
             "serving_runtime": "onnxruntime",
             "no_torch_in_container": true
         }
    3. Test inference with: python -m pytest apps/modelserver/tests/ -v
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import joblib
import numpy as np


def _compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_pipeline(model_card_path: Path):
    with model_card_path.open("r", encoding="utf-8") as f:
        card = json.load(f)

    artifact_meta = card.get("artifact", {})
    artifact_path = model_card_path.parent / artifact_meta["path"]

    if not artifact_path.exists():
        sys.exit(f"ERROR: Artifact not found: {artifact_path}")

    actual_sha256 = _compute_sha256(artifact_path)
    expected_sha256 = artifact_meta.get("sha256", "")
    if expected_sha256 and actual_sha256 != expected_sha256:
        sys.exit(
            f"ERROR: SHA-256 mismatch.\n"
            f"  Expected: {expected_sha256}\n"
            f"  Actual:   {actual_sha256}"
        )

    print(f"Loading artifact: {artifact_path}")
    pipeline = joblib.load(artifact_path)
    return pipeline, card


def export(model_card_path: Path, output_path: Path) -> None:
    try:
        from skl2onnx import convert_sklearn
        from skl2onnx.common.data_types import StringTensorType
    except ImportError:
        sys.exit(
            "ERROR: skl2onnx is not installed.\n"
            "  pip install skl2onnx onnxruntime"
        )

    pipeline, card = _load_pipeline(model_card_path)

    print("Converting sklearn pipeline to ONNX...")

    # Text classifiers take a single column of strings as input.
    # Shape [None, 1] means variable batch size, 1 feature (the message string).
    initial_type = [("message", StringTensorType([None, 1]))]

    try:
        onnx_model = convert_sklearn(
            pipeline,
            initial_types=initial_type,
            target_opset=17,
            options={type(pipeline.steps[-1][1]): {"zipmap": False}},
        )
    except Exception as e:
        sys.exit(
            f"ERROR: ONNX conversion failed: {e}\n\n"
            "Possible causes:\n"
            "  - The pipeline uses a custom transformer not supported by skl2onnx.\n"
            "  - The FeatureUnion with char+word TF-IDF requires skl2onnx >= 1.17.\n"
            "  Try: pip install --upgrade skl2onnx"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        f.write(onnx_model.SerializeToString())

    sha256 = _compute_sha256(output_path)
    size_kb = output_path.stat().st_size / 1024

    print(f"\nExport complete:")
    print(f"  Output:  {output_path}")
    print(f"  Size:    {size_kb:.1f} KB")
    print(f"  SHA-256: {sha256}")

    _verify_onnx(output_path, pipeline)

    print("\nUpdate model_card.json with:")
    print(json.dumps({
        "artifact": {
            "path": output_path.name,
            "sha256": sha256,
            "format": "onnx",
            "serving_runtime": "onnxruntime",
            "no_torch_in_container": True,
        }
    }, indent=2))


def _verify_onnx(onnx_path: Path, original_pipeline) -> None:
    """Run a smoke test comparing ONNX output to the original sklearn pipeline."""

    try:
        import onnxruntime as ort
    except ImportError:
        print("WARNING: onnxruntime not installed, skipping verification.")
        return

    session = ort.InferenceSession(str(onnx_path))
    input_name = session.get_inputs()[0].name

    test_messages = [
        "What are your business hours?",
        "Buy now pricing",
        "Talk to a human",
        "CLICK HERE FREE MONEY",
        "I need help with my account",
    ]

    print("\nVerifying ONNX output matches sklearn pipeline...")
    all_match = True

    for msg in test_messages:
        sklearn_pred = str(original_pipeline.predict([msg])[0])
        onnx_result = session.run(None, {input_name: np.array([[msg]])})
        onnx_pred = str(onnx_result[0][0])

        match = sklearn_pred == onnx_pred
        status = "OK" if match else "MISMATCH"
        print(f"  [{status}] '{msg[:40]}' → sklearn={sklearn_pred}, onnx={onnx_pred}")

        if not match:
            all_match = False

    if all_match:
        print("  All predictions match.")
    else:
        print("\nWARNING: Some predictions differ between sklearn and ONNX.")
        print("Review the mismatches before updating model_card.json.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export classifier to ONNX")
    parser.add_argument(
        "--model-card",
        type=Path,
        default=Path("apps/modelserver/artifacts/model/model_card.json"),
        help="Path to model_card.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("apps/modelserver/artifacts/model/concierge_classifier.onnx"),
        help="Output path for the ONNX model",
    )
    args = parser.parse_args()

    if not args.model_card.exists():
        sys.exit(f"ERROR: model_card.json not found: {args.model_card}")

    export(args.model_card, args.output)


if __name__ == "__main__":
    main()
