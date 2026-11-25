"""BioD descriptive analysis. No UI or file-system side effects."""
from __future__ import annotations

import io
import hashlib
import json
import zipfile
from html import escape

import numpy as np
import pandas as pd

try:
    from scipy.stats import ttest_ind
except ImportError:
    ttest_ind = None

KEY = ["profile", "organ", "timepoint_hour"]
AUC_METHODS = {
    "observed": "관측 구간만 적분 (0시간 외삽 없음)",
    "hold": "0시간 = 첫 측정값 (기존 방식)",
    "zero": "0시간 = 0 (첫 측정점까지 선형 연결)",
}


def prepare(raw):
    df = raw.copy()
    for col, default in [("source_file", "Unknown"), ("source_cro", "Unknown"),
                         ("animal_id", ""), ("row_type", "raw")]:
        if col not in df:
            df[col] = default
        df[col] = df[col].fillna(default).astype(str)
    if "source_id" not in df:
        df["source_id"] = df.source_file
    # JSON tuple prevents ambiguous concatenated identifiers from merging studies.
    df["profile"] = df.apply(lambda r: json.dumps(
        [r.source_cro, r.source_id, str(r.group_id)], ensure_ascii=False), axis=1)
    df["label"] = df["display_group_id"].astype(str) + " | " + df["source_file"]
    collisions = df[["profile", "label"]].drop_duplicates()["label"].duplicated(keep=False)
    if collisions.any():
        df["label"] += " | " + df["group_id"].astype(str) + " | " + df.profile.map(lambda s: hashlib.sha256(s.encode()).hexdigest()[:8])
    for col in ["percent_id_per_g", "timepoint_hour"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["organ"] = df["organ"].astype(str).str.strip().str.title().replace(
        {"Tumour": "Tumor", "Kidneys": "Kidney", "Lungs": "Lung"})
    valid = (np.isfinite(df.percent_id_per_g) & np.isfinite(df.timepoint_hour)
             & (df.timepoint_hour >= 0) & (df.percent_id_per_g >= 0))
    issues = [{"issue": "시간/측정값 결측·비수치·음수 제외", "rows": int((~valid).sum())}]
    df = df.loc[valid].copy()
    identified = df.animal_id.str.strip().str.lower().isin(["", "nan", "none", "unknown"]) == False
    duplicate = identified & df.duplicated(KEY + ["animal_id"], keep=False)
    df["duplicate_animal"] = duplicate
    issues.append({"issue": "동일 파일·그룹·장기·시간의 개체 ID 중복 (검정 제외)", "rows": int(duplicate.sum())})
    return df, pd.DataFrame(issues)


def summarize(df):
    result = df.groupby(KEY, as_index=False).agg(
        label=("label", "first"), source_cro=("source_cro", "first"),
        source_file=("source_file", "first"), mean=("percent_id_per_g", "mean"),
        sd=("percent_id_per_g", "std"), rows=("percent_id_per_g", "size"),
        summary_input=("row_type", lambda x: bool(x.ne("raw").any())))
    result.loc[result.summary_input, "sd"] = np.nan
    return result.sort_values(KEY).reset_index(drop=True)


def integrate_curve(times, values, method, start, end):
    """Linear trapezoids on a fixed window; only explicitly requested origin extrapolation."""
    if method not in AUC_METHODS:
        raise ValueError("Unknown AUC method")
    points = pd.DataFrame({"t": times, "v": values}).dropna().groupby("t").v.mean().sort_index()
    if len(points) < 2 or not np.isfinite([start, end]).all() or start < 0 or end <= start:
        return np.nan, "측정점 2개 이상 및 유효한 적분 구간 필요"
    t, v = points.index.to_numpy(float), points.to_numpy(float)
    if method != "observed" and t[0] > 0:
        v = np.insert(v, 0, v[0] if method == "hold" else 0.0)
        t = np.insert(t, 0, 0.0)
    if start < t[0] or end > t[-1]:
        return np.nan, "선택 구간을 포함하는 관측값 부족 (외삽 안 함)"
    inner = (t > start) & (t < end)
    grid = np.r_[start, t[inner], end]
    y = np.interp(grid, t, v)
    # Explicit trapezoids support both NumPy 1.x and 2.x.
    return float(np.sum(np.diff(grid) * (y[1:] + y[:-1]) / 2)), "ok"


def auc_table(summary, method, start, end):
    records = []
    for (profile, organ), g in summary.groupby(["profile", "organ"]):
        auc, status = integrate_curve(g.timepoint_hour, g["mean"], method, start, end)
        records.append(dict(profile=profile, label=g.label.iloc[0], organ=organ, auc=auc,
                            start_h=start, end_h=end, method=method, points=len(g), status=status))
    return pd.DataFrame(records, columns=["profile", "label", "organ", "auc", "start_h", "end_h", "method", "points", "status"])


def ratio_tables(summary, aucs, tumor):
    num = summary[summary.organ == tumor][["profile", "timepoint_hour", "mean"]].rename(columns={"mean": "tumor_mean"})
    ratios = summary[summary.organ != tumor].merge(num, on=["profile", "timepoint_hour"], how="left")
    ratios["tumor_to_organ"] = ratios.tumor_mean / ratios["mean"].where(ratios["mean"] > 0)
    ratios["ratio_status"] = np.where(ratios.tumor_mean.isna(), "동일 시점 Tumor 없음",
                                        np.where(ratios["mean"] <= 0, "분모 0", "ok"))
    an = aucs[aucs.organ == tumor][["profile", "auc"]].rename(columns={"auc": "tumor_auc"})
    ar = aucs[aucs.organ != tumor].merge(an, on="profile", how="left")
    ar["auc_ratio"] = ar.tumor_auc / ar.auc.where(ar.auc > 0)
    ar["ratio_status"] = np.where(ar.tumor_auc.isna() | ar.auc.isna(), "공통 구간 AUC 부족",
                                    np.where(ar.auc <= 0, "분모 0", "ok"))
    return ratios, ar


def retention_table(summary, early, late):
    cols = ["profile", "organ"]
    a = summary[summary.timepoint_hour == early][cols + ["label", "mean"]].rename(columns={"mean": "early_mean"})
    b = summary[summary.timepoint_hour == late][cols + ["mean"]].rename(columns={"mean": "late_mean"})
    out = a.merge(b, on=cols, how="outer").merge(
        summary[["profile", "label"]].drop_duplicates().rename(columns={"label": "fallback_label"}), on="profile", how="left")
    out["label"] = out.label.fillna(out.fallback_label)
    out = out.drop(columns="fallback_label")
    out["early_h"], out["late_h"] = early, late
    out["retention_pct"] = 100 * out.late_mean / out.early_mean.where(out.early_mean > 0)
    if late <= early:
        out["retention_pct"] = np.nan
    out["decrease_pct"] = 100 - out.retention_pct
    declining = (out.early_mean > out.late_mean) & (out.late_mean > 0) & (late > early)
    out["k_app_per_h"] = np.nan
    out.loc[declining, "k_app_per_h"] = np.log(out.loc[declining, "early_mean"] / out.loc[declining, "late_mean"]) / (late - early)
    out["apparent_half_life_h"] = np.log(2) / out.k_app_per_h
    out["status"] = np.select(
        [out.retention_pct.isna(), declining],
        ["두 시점 값/양수 초기값/시간 순서 확인", "두 점 기반 겉보기 감소"],
        default="증가·동일·후기값 0: 반감기 미산출")
    return out


def bh_adjust(pvalues):
    p = np.asarray(pvalues, float)
    q = np.full(len(p), np.nan)
    valid = np.flatnonzero(np.isfinite(p))
    ordered = valid[np.argsort(p[valid])]
    if len(ordered):
        adjusted = p[ordered] * len(ordered) / np.arange(1, len(ordered) + 1)
        q[ordered] = np.minimum.accumulate(adjusted[::-1])[::-1].clip(0, 1)
    return q


def reference_comparison(raw, summary, reference, independence_confirmed=False):
    ref = summary[summary.profile == reference][["organ", "timepoint_hour", "mean"]].rename(columns={"mean": "reference_mean"})
    out = summary[summary.profile != reference].merge(ref, on=["organ", "timepoint_hour"], how="left")
    out["change_pct"] = 100 * (out["mean"] / out.reference_mean.where(out.reference_mean > 0) - 1)
    out["p_value"] = np.nan
    out["n_candidate"], out["n_reference"] = 0, 0
    out["test_status"] = ""
    groups = {key: g for key, g in raw.groupby(KEY)}
    for i, row in out.iterrows():
        a = groups.get((row.profile, row.organ, row.timepoint_hour), pd.DataFrame())
        b = groups.get((reference, row.organ, row.timepoint_hour), pd.DataFrame())
        status = "ok"
        if a.empty or b.empty:
            status = "동일 시점 Reference 없음"
        elif a.row_type.ne("raw").any() or b.row_type.ne("raw").any():
            status = "평균값 입력: 검정 제외"
        elif a.duplicate_animal.any() or b.duplicate_animal.any():
            status = "개체 ID 중복: 검정 제외"
        elif any(g.animal_id.str.strip().str.lower().isin(["", "nan", "none", "unknown"]).any() for g in [a, b]):
            status = "개체 ID 없음: 검정 제외"
        else:
            out.loc[i, ["n_candidate", "n_reference"]] = [len(a), len(b)]
            if min(len(a), len(b)) < 2:
                status = "군별 독립 개체 2개 이상 필요"
            elif not independence_confirmed:
                status = "독립군·시험 조건 비교 가능 여부 확인 필요"
            elif ttest_ind is None:
                status = "SciPy 설치 필요"
            elif a.percent_id_per_g.var() == 0 and b.percent_id_per_g.var() == 0:
                status = "양 군 분산 0: 검정 제외"
            else:
                p = float(ttest_ind(a.percent_id_per_g, b.percent_id_per_g, equal_var=True).pvalue)
                if np.isfinite(p):
                    out.loc[i, "p_value"] = p
                else:
                    status = "검정 계산 불가"
        out.loc[i, "test_status"] = status
    out["q_bh"] = bh_adjust(out.p_value)
    return out


def rank_candidates(aucs, tumor, normal, weight=0.5):
    t = aucs[aucs.organ == tumor][["profile", "label", "auc"]].rename(columns={"auc": "tumor_auc"})
    n = aucs[aucs.organ == normal][["profile", "auc"]].rename(columns={"auc": "normal_auc"})
    result = t.merge(n, on="profile", how="inner").dropna(subset=["tumor_auc", "normal_auc"])
    result["auc_ratio"] = result.tumor_auc / result.normal_auc.where(result.normal_auc > 0)
    # Ties receive equal midranks; score is explicitly cohort-relative.
    result["score"] = 100 * (weight * result.tumor_auc.rank(pct=True) + (1 - weight) * result.normal_auc.rank(ascending=False, pct=True))
    result["rank"] = result.score.rank(method="min", ascending=False).astype(int)
    return result.sort_values(["rank", "label"])


def excel_bytes(tables, settings):
    """Export numeric tables and their analysis context without converting labels to formulas."""
    excel = io.BytesIO()
    with pd.ExcelWriter(excel, engine="openpyxl") as writer:
        all_tables = {**tables, "Settings": pd.DataFrame({"setting": list(settings), "value": [str(v) for v in settings.values()]})}
        for name, frame in all_tables.items():
            frame.to_excel(writer, sheet_name=name[:31], index=False)
            ws = writer.sheets[name[:31]]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for row in ws.iter_rows():
                for cell in row:
                    # Uploaded labels must remain data, including leading '='.
                    if isinstance(cell.value, str):
                        cell.data_type = "s"
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(55, max(14, len(str(col[0].value)) + 3))
    return excel.getvalue()


def build_report(tables, settings, figures):
    """Downloadable offline HTML + workbook + machine-readable settings."""
    from plotly.offline import get_plotlyjs

    sections = []
    for name, frame in tables.items():
        sections.append(f"<h2>{escape(name)}</h2>" + frame.to_html(index=False, escape=True, na_rep="—", float_format=lambda x: f"{x:.5g}"))
    plots = "".join(fig.to_html(full_html=False, include_plotlyjs=False) for fig in figures)
    metadata = json.dumps(settings, ensure_ascii=False, indent=2, default=str)
    html = ("<!doctype html><html lang='ko'><meta charset='utf-8'><title>BioD Report</title>"
            "<style>body{font:14px system-ui;margin:36px;color:#182230}table{border-collapse:collapse;display:block;overflow:auto}"
            "td,th{padding:7px;border:1px solid #ddd;text-align:left}h2{margin-top:32px}pre{white-space:pre-wrap}@media print{table{font-size:9px}}</style>"
            f"<script>{get_plotlyjs()}</script><h1>BioD Analysis Report</h1><pre>{escape(metadata)}</pre>" + plots + "".join(sections) + "</html>")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("BioD_Report.html", html)
        z.writestr("BioD_Analysis.xlsx", excel_bytes(tables, settings))
        z.writestr("settings.json", metadata)
    return archive.getvalue()
