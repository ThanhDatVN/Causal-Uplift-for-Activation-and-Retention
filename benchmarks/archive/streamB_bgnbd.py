"""
Probabilistic CLV baseline benchmark: load Online Retail II (2 sheet xlsx) -> lam sach ->
RFM -> calibration/holdout theo thoi gian -> fit BG/NBD + Gamma-Gamma.
Dung boi scripts/bench_harness.py de do wall time + peak RAM (du kien nhe,
chi de xac nhan bang so lieu thay vi doan).

Benchmark nay duoc giu lam bang chung thu nghiem cho roadmap Incremental Value
Studio; no khong thuoc pipeline causal production hien tai.

Chay doc lap:
    .venv/Scripts/python.exe benchmarks/streamB_bgnbd.py
"""
import time

import pandas as pd

DATA_PATH = "data/online_retail_II.xlsx"


def load_transactions() -> pd.DataFrame:
    t0 = time.time()
    xls = pd.ExcelFile(DATA_PATH)
    dfs = [pd.read_excel(xls, sheet_name=s) for s in xls.sheet_names]
    df = pd.concat(dfs, ignore_index=True)
    print(f"[load] sheets={xls.sheet_names} rows={len(df):,} time={time.time()-t0:.1f}s", flush=True)

    # lam sach theo mo ta plan: bo CustomerID null, bo Quantity<=0 (tra hang)
    df = df.dropna(subset=["Customer ID"])
    df = df[df["Quantity"] > 0]
    df = df[df["Price"] > 0]
    df["monetary"] = df["Quantity"] * df["Price"]
    print(f"[clean] rows_after={len(df):,}", flush=True)
    return df


def main():
    df = load_transactions()

    from lifetimes.utils import calibration_and_holdout_data, summary_data_from_transaction_data
    from lifetimes import BetaGeoFitter, GammaGammaFitter

    obs_end = df["InvoiceDate"].max()
    cal_end = obs_end - pd.Timedelta(days=180)  # ~6 thang holdout

    t0 = time.time()
    cal_holdout = calibration_and_holdout_data(
        df, "Customer ID", "InvoiceDate",
        calibration_period_end=cal_end,
        observation_period_end=obs_end,
        freq="D",
        monetary_value_col="monetary",
    )
    print(f"[cal_holdout] customers={len(cal_holdout):,} time={time.time()-t0:.1f}s", flush=True)

    t0 = time.time()
    bgf = BetaGeoFitter(penalizer_coef=0.001)
    bgf.fit(cal_holdout["frequency_cal"], cal_holdout["recency_cal"], cal_holdout["T_cal"])
    print(f"[bgnbd] fit_time={time.time()-t0:.1f}s params={dict(bgf.params_)}", flush=True)

    returning = cal_holdout[cal_holdout["frequency_cal"] > 0]
    corr = returning[["frequency_cal", "monetary_value_cal"]].corr().iloc[0, 1]
    print(f"[gammagamma] freq-monetary corr={corr:.4f} (nen |r|<0.3)", flush=True)

    t0 = time.time()
    ggf = GammaGammaFitter(penalizer_coef=0.001)
    ggf.fit(returning["frequency_cal"], returning["monetary_value_cal"])
    print(f"[gammagamma] fit_time={time.time()-t0:.1f}s", flush=True)

    summary = summary_data_from_transaction_data(
        df, "Customer ID", "InvoiceDate", monetary_value_col="monetary", freq="D",
    )
    returning_full = summary[summary["frequency"] > 0]
    clv = ggf.customer_lifetime_value(
        bgf,
        returning_full["frequency"], returning_full["recency"], returning_full["T"],
        returning_full["monetary_value"],
        time=6, freq="D", discount_rate=0.01,
    )
    print(f"[clv] n_customers={len(clv):,} mean_clv_6m={clv.mean():.2f}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
