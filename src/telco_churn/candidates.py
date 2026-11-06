"""The eight screening candidates and three baselines (WP08, runbook §3).

The runbook fixes this list before any screening runs, so that a comparison is
between *declared* recipes rather than between whatever was tried last.  Each
candidate answers one discriminating question:

===== ======================== =============================================
ID    Candidate                Question it answers
===== ======================== =============================================
M01   Control-outcome Logistic Is the simple baseline already good enough?
M02   Control-outcome HGB      Does a nonlinear outcome ranking add value?
M03   S-Logistic               Does a shared linear response reduce noise?
M04   S-HGB                    Does a shared nonlinear surface learn response?
M05   T-Logistic               When does fitting arms separately beat sharing?
M06   T-HGB                    Are there enough events for per-arm models?
M07   DR-Ridge                 Does a linear final stage handle pseudo-noise?
M08   DR-HGB                   Is a nonlinear final stage worth the complexity?
===== ======================== =============================================

Two conventions make the eight comparable, and both are enforced here rather
than trusted:

* **Everything models reward, where higher is better.**  An adverse binary
  outcome is converted by the caller with ``reward = 1 - Y`` before it arrives.
  That is identity I6 of R00, so the sign convention is tested, not assumed.
* **M01 and M02 do not produce effects.**  They rank by predicted control
  outcome.  Their score is on a different scale from the six effect learners,
  which is exactly the point of including them: a ranking baseline that wins
  on policy value says the effect learners are not earning their complexity.
  :attr:`Candidate.score_kind` carries that distinction so a caller cannot
  quietly read a ranking as a calibrated effect.

Hyperparameters are the runbook's, written once here.  Early stopping is off
in screening so fixed iteration counts stay comparable.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline

from .uplift import _augment_s_features, _preprocessor

__all__ = [
    "BASELINES",
    "CANDIDATES",
    "Candidate",
    "CandidateSpec",
    "build_candidate",
    "candidate_ids",
]

ScoreKind = Literal["reward_difference", "outcome_ranking", "constant", "none"]

#: Runbook §3 hyperparameters, in one place so no two candidates drift apart.
LOGISTIC_C = 0.3
HGB_SETTINGS: dict[str, Any] = {
    "learning_rate": 0.05,
    "max_iter": 200,
    "max_leaf_nodes": 15,
    "min_samples_leaf": 100,
    "l2_regularization": 10.0,
    "early_stopping": False,
}
RIDGE_ALPHA = 10.0
NUISANCE_FOLDS = 3
RANDOM_BASELINE_FRACTION = 0.2


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    name: str
    family: str
    question: str
    score_kind: ScoreKind
    trainable: bool = True
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "name": self.name,
            "family": self.family,
            "question": self.question,
            "score_kind": self.score_kind,
            "trainable": self.trainable,
            "note": self.note,
        }


CANDIDATES: tuple[CandidateSpec, ...] = (
    CandidateSpec(
        "M01",
        "Control-outcome Logistic ranking",
        "outcome_ranking",
        "Is the simple baseline already good enough?",
        "outcome_ranking",
    ),
    CandidateSpec(
        "M02",
        "Control-outcome HGB ranking",
        "outcome_ranking",
        "Does a nonlinear outcome ranking add value?",
        "outcome_ranking",
    ),
    CandidateSpec(
        "M03",
        "S-Logistic",
        "s_learner",
        "Does a shared linear response reduce noise?",
        "reward_difference",
        note="treatment x numeric interactions are explicit, not implied",
    ),
    CandidateSpec(
        "M04",
        "S-HGB",
        "s_learner",
        "Does a shared nonlinear surface learn the response?",
        "reward_difference",
    ),
    CandidateSpec(
        "M05",
        "T-Logistic",
        "t_learner",
        "When does fitting arms separately beat sharing?",
        "reward_difference",
    ),
    CandidateSpec(
        "M06",
        "T-HGB",
        "t_learner",
        "Are there enough events for per-arm models?",
        "reward_difference",
    ),
    CandidateSpec(
        "M07",
        "DR-Ridge",
        "dr_learner",
        "Does a linear final stage handle pseudo-outcome noise?",
        "reward_difference",
        note="cross-fitted common nuisances; the final stage is the only difference from M08",
    ),
    CandidateSpec(
        "M08",
        "DR-HGB",
        "dr_learner",
        "Is a nonlinear final stage worth the complexity?",
        "reward_difference",
        note="same pseudo-outcomes as M07",
    ),
)

BASELINES: tuple[CandidateSpec, ...] = (
    CandidateSpec(
        "B01", "No contact", "baseline", "What does doing nothing score?", "none", trainable=False
    ),
    CandidateSpec(
        "B02",
        "Deterministic random contact",
        "baseline",
        "What does spending the budget at random score?",
        "outcome_ranking",
        trainable=False,
        note="selection is a hash of the row id, so it replays identically",
    ),
    CandidateSpec(
        "B03",
        "Constant effect",
        "baseline",
        "Does per-unit targeting beat treating everyone the same?",
        "constant",
        trainable=True,
        note="the constant is estimated on training data only; reading the "
        "evaluation ATE would be circular",
    ),
)

_ALL = {spec.candidate_id: spec for spec in (*CANDIDATES, *BASELINES)}


def candidate_ids(*, include_baselines: bool = False) -> list[str]:
    return [spec.candidate_id for spec in (CANDIDATES if not include_baselines else _ALL.values())]


#: Which override keys each builder understands.  A typo in a tuning grid
#: would otherwise be silently ignored and the whole search would compare a
#: configuration against itself, so unknown keys are refused.
_TUNABLE: dict[str, frozenset[str]] = {
    "logistic": frozenset({"C"}),
    "hgb": frozenset(HGB_SETTINGS),
    "ridge": frozenset({"alpha", "shrinkage"}),
}


def _checked(params: Mapping[str, Any] | None, kind: str) -> dict[str, Any]:
    values = dict(params or {})
    unknown = sorted(set(values) - _TUNABLE[kind])
    if unknown:
        raise ValueError(
            f"{kind} does not take {unknown}; tunable keys are "
            f"{sorted(_TUNABLE[kind])}. A silently ignored override would make a "
            "search compare a configuration against itself."
        )
    return values


def _logistic(
    frame: pd.DataFrame, *, seed: int, params: Mapping[str, Any] | None = None
) -> Pipeline:
    values = _checked(params, "logistic")
    return Pipeline(
        [
            ("preprocess", _preprocessor(frame, dense=False)),
            (
                "model",
                LogisticRegression(
                    C=float(values.get("C", LOGISTIC_C)),
                    max_iter=2_000,
                    solver="liblinear",
                    random_state=seed,
                ),
            ),
        ]
    )


def _hgb_classifier(
    frame: pd.DataFrame, *, seed: int, params: Mapping[str, Any] | None = None
) -> Pipeline:
    settings = {**HGB_SETTINGS, **_checked(params, "hgb")}
    return Pipeline(
        [
            ("preprocess", _preprocessor(frame, dense=True)),
            ("model", HistGradientBoostingClassifier(random_state=seed, **settings)),
        ]
    )


def _hgb_regressor(
    frame: pd.DataFrame, *, seed: int, params: Mapping[str, Any] | None = None
) -> Pipeline:
    settings = {**HGB_SETTINGS, **_checked(params, "hgb")}
    return Pipeline(
        [
            ("preprocess", _preprocessor(frame, dense=True)),
            ("model", HistGradientBoostingRegressor(random_state=seed, **settings)),
        ]
    )


def _ridge(frame: pd.DataFrame, *, seed: int, params: Mapping[str, Any] | None = None) -> Pipeline:
    values = _checked(params, "ridge")
    return Pipeline(
        [
            ("preprocess", _preprocessor(frame, dense=False)),
            ("model", Ridge(alpha=float(values.get("alpha", RIDGE_ALPHA)), random_state=seed)),
        ]
    )


def _positive_probability(model: BaseEstimator, features: pd.DataFrame) -> np.ndarray:
    return np.asarray(model.predict_proba(features)[:, 1], dtype=float)


@dataclass
class Candidate:
    """One fitted (or fit-free) screening candidate.

    ``score`` is what the allocator maximises.  For the six effect learners it
    is an estimated reward difference; for M01/M02 it is a predicted control
    outcome, which ranks but does not measure.  ``score_kind`` says which.
    """

    spec: CandidateSpec
    seed: int = 20260921
    #: Declared overrides for this configuration.  Empty means the runbook
    #: defaults, which is what R02 screened; R03 varies these and nothing
    #: else, so a tuning result cannot be confounded with a recipe change.
    hyperparameters: Mapping[str, Any] = field(default_factory=dict)
    fitted_: bool = field(default=False, init=False)
    _models: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _constant: float = field(default=0.0, init=False, repr=False)
    _shrinkage: float = field(default=1.0, init=False, repr=False)

    @property
    def candidate_id(self) -> str:
        return self.spec.candidate_id

    @property
    def score_kind(self) -> ScoreKind:
        return self.spec.score_kind

    # -- fitting -----------------------------------------------------------
    def fit(
        self,
        features: pd.DataFrame,
        treatment: Sequence[int] | np.ndarray,
        reward: Sequence[float] | np.ndarray,
        *,
        propensity: Sequence[float] | np.ndarray | float | None = None,
    ) -> Candidate:
        """Fit on training rows only.

        ``reward`` is oriented so that higher is better.  ``propensity`` is the
        design probability of the treated arm; the DR learners require it and
        say so rather than silently estimating one.
        """

        arm = np.asarray(treatment, dtype=int)
        value = np.asarray(reward, dtype=float)
        if len(features) != len(arm) or len(features) != len(value):
            raise ValueError("features, treatment and reward must have the same length")
        if set(np.unique(arm)) - {0, 1}:
            raise ValueError("treatment must be binary 0/1 for the screening candidates")

        identifier = self.candidate_id
        if identifier in ("B01", "B02"):
            # Fit-free by construction: one never contacts, the other selects
            # by a hash of the unit id.
            pass
        elif identifier == "B03":
            treated = value[arm == 1]
            control = value[arm == 0]
            if not len(treated) or not len(control):
                raise ValueError("the constant-effect baseline needs both arms in training")
            self._constant = float(treated.mean() - control.mean())
        elif identifier in ("M01", "M02"):
            control_rows = arm == 0
            builder = _logistic if identifier == "M01" else _hgb_classifier
            model = builder(features, seed=self.seed, params=self.hyperparameters)
            model.fit(features.loc[control_rows], value[control_rows].astype(int))
            self._models["control"] = model
        elif identifier in ("M03", "M04"):
            interactions = identifier == "M03"
            augmented = _augment_s_features(features, treatment=arm, interactions=interactions)
            builder = _logistic if identifier == "M03" else _hgb_classifier
            model = builder(augmented, seed=self.seed, params=self.hyperparameters)
            model.fit(augmented, value.astype(int))
            self._models["shared"] = model
            self._models["interactions"] = interactions
        elif identifier in ("M05", "M06"):
            builder = _logistic if identifier == "M05" else _hgb_classifier
            for label in (0, 1):
                rows = arm == label
                if rows.sum() < 2 or len(np.unique(value[rows])) < 2:
                    raise ValueError(f"arm {label} has too little signal to fit {identifier}")
                model = builder(features, seed=self.seed + label, params=self.hyperparameters)
                model.fit(features.loc[rows], value[rows].astype(int))
                self._models[f"arm_{label}"] = model
        elif identifier in ("M07", "M08"):
            if propensity is None:
                raise ValueError(
                    f"{identifier} is a DR learner and needs the design propensity; "
                    "passing None would make it estimate one silently"
                )
            pseudo = self._pseudo_outcome(features, arm, value, propensity)
            builder = _ridge if identifier == "M07" else _hgb_regressor
            model = builder(features, seed=self.seed, params=self.hyperparameters)
            model.fit(features, pseudo)
            self._models["effect"] = model
            # The runbook's DR-Ridge grid shrinks the fitted effect toward the
            # train-only constant effect, so lambda = 1 is the unshrunk model
            # and lambda = 0 is the constant. The constant is estimated here,
            # on training rows, never from what is being scored.
            self._shrinkage = float(self.hyperparameters.get("shrinkage", 1.0))
            self._constant = float(pseudo.mean())
        else:  # pragma: no cover - the registry is closed
            raise ValueError(f"unknown candidate {identifier!r}")

        self.fitted_ = True
        return self

    def _pseudo_outcome(
        self,
        features: pd.DataFrame,
        arm: np.ndarray,
        value: np.ndarray,
        propensity: Sequence[float] | np.ndarray | float,
    ) -> np.ndarray:
        """Cross-fitted doubly robust pseudo-outcome, shared by M07 and M08.

        Cross-fitting matters here: nuisances fitted on the same rows they
        score would let the final stage chase its own residuals.
        """

        e = (
            np.full(len(features), float(propensity))
            if np.isscalar(propensity)
            else np.asarray(propensity, dtype=float)
        )
        if ((e <= 0) | (e >= 1)).any():
            raise ValueError("propensity must lie strictly inside (0, 1) for a DR learner")

        mu0 = np.zeros(len(features), dtype=float)
        mu1 = np.zeros(len(features), dtype=float)
        strata = arm * 2 + (value > np.median(value)).astype(int)
        splitter = StratifiedKFold(n_splits=NUISANCE_FOLDS, shuffle=True, random_state=self.seed)
        for train_index, score_index in splitter.split(features, strata):
            train = features.iloc[train_index]
            score = features.iloc[score_index]
            for label, target in ((0, mu0), (1, mu1)):
                rows = arm[train_index] == label
                if rows.sum() < 2 or len(np.unique(value[train_index][rows])) < 2:
                    target[score_index] = value[train_index][rows].mean() if rows.sum() else 0.0
                    continue
                model = _logistic(train, seed=self.seed + label)
                model.fit(train.loc[rows], value[train_index][rows].astype(int))
                target[score_index] = _positive_probability(model, score)

        residual_1 = np.where(arm == 1, (value - mu1) / e, 0.0)
        residual_0 = np.where(arm == 0, (value - mu0) / (1.0 - e), 0.0)
        return (mu1 - mu0) + residual_1 - residual_0

    # -- scoring -----------------------------------------------------------
    def score(self, features: pd.DataFrame, *, unit_id: Sequence[Any] | None = None) -> np.ndarray:
        """The quantity the allocator maximises, one value per row."""

        if not self.fitted_ and self.spec.trainable:
            raise ValueError(f"{self.candidate_id} has not been fitted")
        identifier = self.candidate_id

        if identifier == "B01":
            # Never positive, so a positive-value allocator contacts nobody.
            return np.zeros(len(features), dtype=float)
        if identifier == "B02":
            if unit_id is None:
                raise ValueError("the random baseline needs unit ids so it can replay identically")
            draws = np.array(
                [
                    int(hashlib.sha256(f"B02:{value}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
                    for value in unit_id
                ]
            )
            # A deterministic pseudo-random score: the top fraction is stable.
            return draws
        if identifier == "B03":
            return np.full(len(features), self._constant, dtype=float)
        if identifier in ("M01", "M02"):
            return _positive_probability(self._models["control"], features)
        if identifier in ("M03", "M04"):
            interactions = bool(self._models["interactions"])
            model = self._models["shared"]
            treated = _augment_s_features(features, treatment=1, interactions=interactions)
            control = _augment_s_features(features, treatment=0, interactions=interactions)
            return _positive_probability(model, treated) - _positive_probability(model, control)
        if identifier in ("M05", "M06"):
            return _positive_probability(self._models["arm_1"], features) - _positive_probability(
                self._models["arm_0"], features
            )
        if identifier in ("M07", "M08"):
            fitted = np.asarray(self._models["effect"].predict(features), dtype=float)
            if self._shrinkage >= 1.0:
                return fitted
            # Shrink toward the train-only constant effect.  Pseudo-outcomes
            # are noisy, so a final stage can fit that noise; lambda trades
            # per-unit resolution for stability, and lambda = 0 collapses to
            # the constant, which is B03's score.
            return self._shrinkage * fitted + (1.0 - self._shrinkage) * self._constant
        raise ValueError(f"unknown candidate {identifier!r}")  # pragma: no cover


def build_candidate(
    candidate_id: str,
    *,
    seed: int = 20260921,
    hyperparameters: Mapping[str, Any] | None = None,
) -> Candidate:
    """Construct one declared candidate by id, optionally reconfigured.

    ``hyperparameters`` is how R03 varies a configuration without touching the
    recipe.  Keys are validated against what the candidate's builder actually
    reads, so a misspelled override fails rather than quietly leaving the
    default in place and making a search compare a model with itself.
    """

    if candidate_id not in _ALL:
        raise ValueError(
            f"unknown candidate {candidate_id!r}; declared: {sorted(_ALL)}. "
            "Adding a model means revising the runbook, not passing a new string."
        )
    return Candidate(
        spec=_ALL[candidate_id], seed=seed, hyperparameters=dict(hyperparameters or {})
    )
