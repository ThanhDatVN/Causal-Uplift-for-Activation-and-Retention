import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.data import load_criteo_full, stratified_sample


@pytest.fixture(scope="session")
def full_df():
    return load_criteo_full()


@pytest.fixture(scope="session")
def sample_5pct(full_df):
    return stratified_sample(full_df, frac=0.05, seed=42)


@pytest.fixture(scope="session")
def sample_1pct(full_df):
    return stratified_sample(full_df, frac=0.01, seed=42)
