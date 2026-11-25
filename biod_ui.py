"""Candidate analysis and a separate portable report view."""
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from biod_analysis import (AUC_METHODS, prepare, summarize, auc_table, ratio_tables,
                           retention_table, reference_comparison, rank_candidates,
                           build_report, ttest_ind)


@st.cache_data(show_spinner="보고서 준비 중...", max_entries=3)
def _report_download(tables, settings, figure_jsons):
    settings = dict(settings, generated_at=datetime.now(ZoneInfo("Asia/Seoul")).isoformat())
    return build_report(tables, settings, [go.Figure(json.loads(s)) for s in figure_jsons])


def _unavailable(report_tab, message):
    st.info(message)
    with report_tab:
        st.subheader("BioD Report")
        st.info(message)


def render_analysis(master, report_tab):
    st.subheader("Candidate Analysis")
    raw, issues = prepare(master)
    if raw.empty:
        _unavailable(report_tab, "유효한 측정값과 시간 데이터가 없습니다.")
        return
    labels = raw[["profile", "label"]].drop_duplicates().set_index("profile").label.to_dict()
    chosen = st.multiselect("비교할 물질", list(labels), default=list(labels), format_func=labels.get, key="analysis_profiles")
    if not chosen:
        _unavailable(report_tab, "분석 대상을 선택해 주세요.")
        return
    raw = raw[raw.profile.isin(chosen)].copy()
    summary = summarize(raw)
    organs = sorted(summary.organ.unique())
    times = sorted(summary.timepoint_hour.unique())
    col1, col2, col3 = st.columns(3)
    tumor = col1.selectbox("표적 장기", organs, index=organs.index("Tumor") if "Tumor" in organs else 0)
    normal_options = [o for o in organs if o != tumor]
    if not normal_options:
        _unavailable(report_tab, "비율과 순위 분석에는 서로 다른 장기가 2개 이상 필요합니다.")
        return
    normal = col2.selectbox("비교 장기", normal_options, index=normal_options.index("Kidney") if "Kidney" in normal_options else 0)
    reference = col3.selectbox("Reference", chosen, format_func=labels.get)

    limits = summary[summary.organ.isin([tumor, normal])].groupby(["profile", "organ"]).timepoint_hour.agg(["min", "max"])
    common_start, common_end = float(limits["min"].max()), float(limits["max"].min())
    overlap = common_start <= common_end
    if not overlap:
        common_start, common_end = float(times[0]), float(times[-1])
    with st.expander("세부 계산 설정"):
        method = st.selectbox("AUC 계산 방식", list(AUC_METHODS), format_func=AUC_METHODS.get, key="analysis_auc_method")
        time_options = sorted(set(times) | ({0.0} if method != "observed" else set()))
        default_start = common_start if method == "observed" else 0.0
        start, end = st.select_slider("분석 시간 범위 (h)", options=time_options,
                                     value=(default_start, common_end), format_func=lambda h: f"{h:g}h",
                                     key=f"analysis_auc_window_{method}")
        st.caption("기본값은 선택한 물질의 표적·비교 장기가 겹치는 관측 구간입니다. 실측 시간점으로 범위를 바꿀 수 있습니다. "
                   "0시간 가정은 실제 0시간 측정값이 없을 때만 적용하며, 마지막 관측 이후는 외삽하지 않습니다.")
    st.caption(f"분석 구간 {start:g}–{end:g}h · {AUC_METHODS[method]}")
    if not overlap or end <= start:
        st.warning("모든 물질을 비교할 수 있는 공통 시간 구간이 부족합니다. 비교할 물질이나 세부 계산 설정의 범위를 확인해 주세요.")
    aucs = auc_table(summary, method, start, end)
    ratios, auc_ratios = ratio_tables(summary, aucs, tumor)
    weight = 0.5
    ranking = rank_candidates(aucs, tumor, normal, weight)
    tabs = st.tabs(["후보 비교", "장기 비율", "유지율·감소율", "Reference 비교"])
    figures = []
    threshold = "unavailable"
    with tabs[0]:
        st.caption("표적 장기 AUC는 높고, 비교 장기 AUC는 낮은 정도를 동일하게 반영한 참고 순위입니다.")
        st.write(f"비교 가능 {len(ranking)} / {len(chosen)}개 물질")
        display = ranking[["rank", "label", "tumor_auc", "normal_auc", "auc_ratio"]].rename(columns={
            "rank": "순위", "label": "물질", "tumor_auc": f"{tumor} AUC", "normal_auc": f"{normal} AUC", "auc_ratio": f"{tumor}/{normal} AUC 비율"})
        st.dataframe(display, hide_index=True, use_container_width=True)
        if not ranking.empty:
            refrow = ranking[ranking.profile == reference]
            threshold = "Reference" if not refrow.empty else "중앙값"
            xcut = float(refrow.normal_auc.iloc[0] if threshold == "Reference" else ranking.normal_auc.median())
            ycut = float(refrow.tumor_auc.iloc[0] if threshold == "Reference" else ranking.tumor_auc.median())
            ranking["quadrant"] = [
                "표적↑ / 비교장기↓" if y >= ycut and x <= xcut else
                "표적↑ / 비교장기↑" if y >= ycut else
                "표적↓ / 비교장기↓" if x <= xcut else "표적↓ / 비교장기↑"
                for x, y in zip(ranking.normal_auc, ranking.tumor_auc)]
            fig = px.scatter(ranking, x="normal_auc", y="tumor_auc", color="quadrant", hover_name="label", hover_data=["rank", "auc_ratio"],
                             labels={"normal_auc": f"{normal} AUC (%ID/g·h) ↓", "tumor_auc": f"{tumor} AUC (%ID/g·h) ↑"}, title="Candidate Quadrant")
            fig.add_vline(x=xcut, line_dash="dash")
            fig.add_hline(y=ycut, line_dash="dash")
            fig.update_traces(marker_size=14)
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"왼쪽 위일수록 표적 분포가 높고 비교 장기 분포가 낮습니다. 점선 기준: {threshold}.")
            figures.append(fig)
        else:
            st.info("표적·비교 장기의 선택 구간 AUC가 모두 있는 물질이 없습니다.")
        with st.expander("계산 방법 및 AUC 상세"):
            st.caption("표적 AUC의 높은 순위 백분위와 비교 장기 AUC의 낮은 순위 백분위를 1:1로 반영합니다. "
                       "동점은 같은 순위이며, 선택한 물질에 따라 순위가 달라집니다. 통계적 유의성을 뜻하지 않습니다. AUC 단위: %ID/g·h.")
            st.dataframe(aucs.drop(columns="profile"), hide_index=True)
    with tabs[1]:
        st.caption("시점별 비율 = 표적 평균 / 장기 평균. AUC 비율 = 같은 분석 구간의 표적 AUC / 장기 AUC. 분모가 0이거나 짝이 없으면 계산하지 않습니다.")
        st.dataframe(ratios.drop(columns="profile"), hide_index=True, use_container_width=True)
        st.dataframe(auc_ratios.drop(columns="profile"), hide_index=True, use_container_width=True)
        valid_ratios = ratios.dropna(subset=["tumor_to_organ"])
        if not valid_ratios.empty:
            ratio_organ = st.selectbox("비율 추이 장기", sorted(valid_ratios.organ.unique()))
            fig = px.line(valid_ratios[valid_ratios.organ == ratio_organ].sort_values("timepoint_hour"), x="timepoint_hour", y="tumor_to_organ", color="label", markers=True,
                          title=f"{tumor}/{ratio_organ}", labels={"timepoint_hour": "Time (h)", "tumor_to_organ": "Ratio"})
            st.plotly_chart(fig, use_container_width=True)
            figures.append(fig)
    with tabs[2]:
        c1, c2 = st.columns(2)
        early = c1.selectbox("초기 시점 (h)", times, key="retention_early")
        late = c2.selectbox("후기 시점 (h)", times, index=len(times) - 1, key="retention_late")
        retention = retention_table(summary, early, late)
        st.caption("유지율 = 후기/초기 × 100. 감소율 = 100 − 유지율. 겉보기 반감기는 감소하는 양수 두 점에서만 계산하며, 전신 청소율(CL)이나 말단 반감기가 아닙니다.")
        st.dataframe(retention.drop(columns="profile"), hide_index=True, use_container_width=True)
    with tabs[3]:
        independent = st.checkbox("선택한 후보군과 Reference는 서로 독립된 개체군이며, 투여량·측정 조건·시험 설계를 비교할 수 있습니다.", value=False, key="analysis_independent")
        comparisons = reference_comparison(raw, summary, reference, independent)
        st.caption("증감률 = (후보 평균/Reference 평균 − 1) × 100. 같은 장기·시점끼리 비교합니다. "
                   "검정은 개체 원자료가 있을 때 양측 Welch t-test와 전체 유효 검정의 BH FDR 보정을 적용합니다. AUC·비율은 검정하지 않습니다.")
        if ttest_ind is None:
            st.warning("SciPy 설치 후 통계 검정을 사용할 수 있습니다.")
        st.dataframe(comparisons.drop(columns="profile"), hide_index=True, use_container_width=True)

    with report_tab:
        st.subheader("BioD Report")
        st.write("Candidate Analysis에서 선택한 물질과 조건을 보고서로 저장합니다.")
        st.caption(f"{len(chosen)}개 물질 · {tumor}/{normal} · {start:g}–{end:g}h · Reference: {labels[reference]}")
        st.caption("ZIP 구성: 오프라인 HTML 보고서, Excel 결과표·표준화 원자료, 분석 설정 JSON")
        target_curve = summary[summary.organ == tumor].sort_values("timepoint_hour")
        if not target_curve.empty:
            figures.append(px.line(target_curve, x="timepoint_hour", y="mean", color="label", markers=True,
                                   title=f"{tumor} Time–Activity Curve", labels={"timepoint_hour": "Time (h)", "mean": "%ID/g"}))
        last_biod = summary[summary.timepoint_hour == late]
        if not last_biod.empty:
            figures.append(px.bar(last_biod, x="organ", y="mean", color="label", barmode="group",
                                  title=f"Whole BioD · {late:g} h", labels={"mean": "%ID/g"}))
        settings = dict(reference=labels[reference], target=tumor, comparator=normal,
                        auc_method=AUC_METHODS[method], start_h=start, end_h=end,
                        early_h=early, late_h=late, tumor_weight=weight,
                        independent_groups_confirmed=independent, selected_profiles=[labels[p] for p in chosen],
                        statistics="Two-sided Welch; BH FDR over all valid selected comparisons",
                        ratios="Ratio of group means; ratio of AUCs on fixed common interval",
                        retention="Two-timepoint apparent decline; not systemic CL or terminal half-life",
                        summary_input="rows counts input records, not necessarily animals; SD omitted for summary inputs",
                        quadrant_threshold=threshold,
                        interpretation="Exploratory cohort-relative ranking; equal weight for target and comparator")
        tables = dict(Summary=summary, AUC=aucs, Ratios=ratios, AUC_Ratios=auc_ratios,
                      Retention=retention, Reference=comparisons, Ranking=ranking, Quality=issues, Raw_Data=raw)
        digest = hashlib.sha256(pd.util.hash_pandas_object(raw, index=True).values.tobytes() + json.dumps(settings, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        report = _report_download(tables, settings, tuple(fig.to_json() for fig in figures))
        st.download_button("One-click BioD Report 다운로드", data=report, file_name=f"BioD_Report_{digest}.zip", mime="application/zip", key=f"report_{digest}", type="primary")
        with st.expander("보고서 포함 항목 및 데이터 확인"):
            st.write("평균·AUC, 후보 순위·Quadrant, 장기 비율, 유지율·감소율, Reference 비교, 분석에 사용한 표준화 원자료")
            st.dataframe(issues, hide_index=True)
