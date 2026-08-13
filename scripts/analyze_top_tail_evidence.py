"""Audit the post-hoc 1%-2% signal without turning it into model selection.

The two fold seeds use the same source rows.  Bootstrap multiplicities are therefore
kept identical across seeds, candidates, and budgets, and a single simultaneous band
is constructed for the complete registered family.  The resulting intervals are
conditional on the frozen OOF scores; training instability is reported separately as
top-tail membership overlap.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.policy_evaluation import (
    paired_policy_area_bootstrap,
    paired_policy_difference_band,
    top_tail_event_support,
    top_tail_overlap,
)
from src.experiment import git_state


DEFAULT_PROTOCOL = Path("configs/top_tail_research_protocol_v2.json")
DEFAULT_OUTPUT_DIR = Path("output/improvement/top_tail_research_v2")
RESERVED_KEYS = {
    "source_index",
    "treatment",
    "outcome",
    "dr_signal",
    "adjusted_signal",
    "mu0",
    "mu1",
}
OUTPUT_FILENAMES = (
    "simultaneous_tail_differences.csv",
    "tail_event_support.csv",
    "tail_membership_overlap.csv",
    "analysis_summary.json",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_run(run_dir: Path) -> tuple[dict, dict[str, np.ndarray]]:
    manifest = json.loads((run_dir / "run_manifest.json").read_text("utf-8"))
    with np.load(run_dir / "oof_scores.npz") as payload:
        arrays = {key: payload[key].copy() for key in payload.files}
    return manifest, arrays


def _assert_comparable(
    manifests: dict[int, dict],
    arrays: dict[int, dict[str, np.ndarray]],
    family: list[str],
) -> None:
    seeds = list(manifests)
    first_seed = seeds[0]
    first_manifest = manifests[first_seed]
    first = arrays[first_seed]
    for seed in seeds:
        manifest = manifests[seed]
        current = arrays[seed]
        if int(manifest["fold_seed"]) != int(seed):
            raise ValueError(
                f"Run-dir seed {seed} khai bao fold_seed={manifest['fold_seed']}"
            )
        for field in (
            "protocol_id",
            "stage",
            "outcome",
            "pool_fraction",
            "pool_seed",
            "n_folds",
            "propensity",
            "budget_grid",
        ):
            if manifest.get(field) != first_manifest.get(field):
                raise ValueError(
                    f"Fold seed {seed} khac comparison contract o {field}: "
                    f"{first_manifest.get(field)!r} != {manifest.get(field)!r}"
                )
        if manifest["development_index_sha256"] != first_manifest[
            "development_index_sha256"
        ]:
            raise ValueError("Fold seeds không dùng cùng development population")
        for key in ("source_index", "treatment", "outcome"):
            if not np.array_equal(current[key], first[key]):
                raise ValueError(f"Fold seed {seed} không căn hàng chính xác ở {key}")
        missing = [name for name in family if name not in current]
        if missing:
            raise ValueError(f"Fold seed {seed} thiếu registered models: {missing}")


def _global_band(
    bootstraps: dict[int, dict],
    reference: str,
    challengers: list[str],
) -> dict:
    """Combine seed-specific paired differences under shared bootstrap draws."""
    observed_parts = []
    draw_parts = []
    labels = []
    budgets = None
    n_boot = None
    for seed, bootstrap in bootstraps.items():
        names = bootstrap["model_names"]
        reference_index = names.index(reference)
        indices = [names.index(name) for name in challengers]
        observed_parts.append(
            bootstrap["observed_curve"][indices]
            - bootstrap["observed_curve"][reference_index]
        )
        draw_parts.append(
            bootstrap["curve_draws"][:, indices, :]
            - bootstrap["curve_draws"][:, reference_index : reference_index + 1, :]
        )
        labels.extend([f"{name}@seed{seed}" for name in challengers])
        if budgets is None:
            budgets = bootstrap["budget_fraction"]
            n_boot = bootstrap["curve_draws"].shape[0]
        elif not np.array_equal(budgets, bootstrap["budget_fraction"]):
            raise ValueError("Budget grid khác nhau giữa fold seeds")
        elif n_boot != bootstrap["curve_draws"].shape[0]:
            raise ValueError("Số bootstrap draws khác nhau giữa fold seeds")

    observed_difference = np.concatenate(observed_parts, axis=0)
    difference_draws = np.concatenate(draw_parts, axis=1)
    assert budgets is not None and n_boot is not None
    synthetic_result = {
        "model_names": ["zero_reference", *labels],
        "budget_fraction": budgets,
        "observed_curve": np.concatenate(
            [np.zeros((1, len(budgets))), observed_difference],
            axis=0,
        ),
        "curve_draws": np.concatenate(
            [
                np.zeros((n_boot, 1, len(budgets))),
                difference_draws,
            ],
            axis=1,
        ),
    }
    return paired_policy_difference_band(
        synthetic_result,
        reference="zero_reference",
        candidates=labels,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--n-boot", type=int, default=None)
    args = parser.parse_args()

    protocol = json.loads(args.protocol.read_text("utf-8"))
    audit = protocol["retrospective_audit"]
    reference = audit["reference"]
    family = list(audit["registered_family"])
    challengers = [name for name in family if name != reference]
    causal_candidates = set(audit["causal_candidates"])
    budgets = np.asarray(audit["budget_grid"], dtype="float64")
    registered_n_boot = int(audit["bootstrap_replicates"])
    if args.n_boot is not None and int(args.n_boot) != registered_n_boot:
        raise ValueError(
            f"n_boot={args.n_boot} khac protocol={registered_n_boot}; "
            "dung output-dir moi va protocol moi cho sensitivity run"
        )
    n_boot = registered_n_boot
    bootstrap_seed = int(audit["bootstrap_seed"])

    if args.output_dir.exists() and any(
        (args.output_dir / filename).exists() for filename in OUTPUT_FILENAMES
    ):
        raise FileExistsError(
            f"Output audit da ton tai o {args.output_dir}; dung namespace moi de "
            "khong ghi de bang chung da dong bang"
        )

    manifests = {}
    arrays = {}
    input_artifacts = {}
    for seed_text, directory in audit["run_dirs"].items():
        seed = int(seed_text)
        run_dir = Path(directory)
        manifests[seed], arrays[seed] = _load_run(run_dir)
        input_artifacts[str(seed)] = {
            "run_dir": run_dir.as_posix(),
            "manifest_sha256": _sha256_file(run_dir / "run_manifest.json"),
            "oof_scores_sha256": _sha256_file(run_dir / "oof_scores.npz"),
        }
    _assert_comparable(manifests, arrays, family)

    bootstraps = {}
    support_rows = []
    for seed, payload in arrays.items():
        scores = {name: payload[name].astype("float64") for name in family}
        # Same n, RNG seed, and draw count deliberately reproduce the same row
        # multiplicities across fold seeds for the global paired family.
        bootstraps[seed] = paired_policy_area_bootstrap(
            scores,
            payload["dr_signal"],
            budgets=budgets,
            n_boot=n_boot,
            seed=bootstrap_seed,
        )
        for name in family:
            for row in top_tail_event_support(
                payload["outcome"],
                payload["treatment"],
                payload[name],
                budgets,
            ):
                support_rows.append({"fold_seed": seed, "model": name, **row})

    band = _global_band(bootstraps, reference, challengers)
    band_rows = []
    for label_index, label in enumerate(band["candidate_names"]):
        name, seed_text = label.rsplit("@seed", maxsplit=1)
        for budget_index, budget in enumerate(band["budget_fraction"]):
            band_rows.append(
                {
                    "fold_seed": int(seed_text),
                    "model": name,
                    "reference": reference,
                    "is_causal_candidate": name in causal_candidates,
                    "budget_fraction": float(budget),
                    "observed_difference": float(
                        band["observed_difference"][label_index, budget_index]
                    ),
                    "pointwise_ci_low": float(
                        band["pointwise_ci_low"][label_index, budget_index]
                    ),
                    "pointwise_ci_high": float(
                        band["pointwise_ci_high"][label_index, budget_index]
                    ),
                    "simultaneous_ci_low": float(
                        band["simultaneous_ci_low"][label_index, budget_index]
                    ),
                    "simultaneous_ci_high": float(
                        band["simultaneous_ci_high"][label_index, budget_index]
                    ),
                    "standard_error": float(
                        band["standard_error"][label_index, budget_index]
                    ),
                    "critical_value": band["critical_value"],
                    "family_size": band["family_size"],
                    "n_boot": band["n_boot"],
                    "inference_scope": band["scope"],
                }
            )

    seed_a, seed_b = list(arrays)
    overlap_rows = []
    for name in family:
        for row in top_tail_overlap(
            arrays[seed_a][name],
            arrays[seed_b][name],
            budgets,
        ):
            overlap_rows.append(
                {
                    "model": name,
                    "fold_seed_a": seed_a,
                    "fold_seed_b": seed_b,
                    **row,
                }
            )

    band_frame = pd.DataFrame(band_rows)
    support_frame = pd.DataFrame(support_rows)
    overlap_frame = pd.DataFrame(overlap_rows)
    causal_band = band_frame.loc[band_frame["is_causal_candidate"]]
    summary = {
        "analysis_schema_version": 2,
        "protocol_id": protocol["protocol_id"],
        "protocol_path": args.protocol.as_posix(),
        "protocol_sha256": _sha256_file(args.protocol),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "code_state": git_state(),
        "input_artifacts": input_artifacts,
        "analysis_kind": "post_hoc_retrospective_audit_not_model_selection",
        "source_population_sha256": next(iter(manifests.values()))[
            "development_index_sha256"
        ],
        "n_rows": int(len(next(iter(arrays.values()))["outcome"])),
        "fold_seeds": list(arrays),
        "budgets": budgets.tolist(),
        "registered_challengers": challengers,
        "family_size": band["family_size"],
        "n_boot": n_boot,
        "bootstrap_seed": bootstrap_seed,
        "critical_value": band["critical_value"],
        "all_causal_point_differences_positive": bool(
            (causal_band["observed_difference"] > 0).all()
        ),
        "any_causal_simultaneous_lower_bound_positive": bool(
            (causal_band["simultaneous_ci_low"] > 0).any()
        ),
        "all_causal_simultaneous_lower_bounds_positive": bool(
            (causal_band["simultaneous_ci_low"] > 0).all()
        ),
        "minimum_causal_overlap_fraction": float(
            overlap_frame.loc[
                overlap_frame["model"].isin(causal_candidates),
                "overlap_fraction",
            ].min()
        ),
        "minimum_control_events_in_causal_tail": int(
            support_frame.loc[
                support_frame["model"].isin(causal_candidates),
                "control_events",
            ].min()
        ),
        "inference_scope": band["scope"],
        "training_uncertainty_in_interval": False,
        "decision": "retain_response_and_carry_hypothesis_to_new_preregistered_data",
        "promotion_allowed": False,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    band_frame.to_csv(args.output_dir / "simultaneous_tail_differences.csv", index=False)
    support_frame.to_csv(args.output_dir / "tail_event_support.csv", index=False)
    overlap_frame.to_csv(args.output_dir / "tail_membership_overlap.csv", index=False)
    (args.output_dir / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(band_frame.to_string(index=False))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
