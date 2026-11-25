"""Additional analysis workspace, kept separate from legacy CRO parsers."""
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


def render_analysis(master):
    st.subheader("BioD 의사결정 분석")
    st.caption("파일·CRO·원래 그룹별로 분리해 분석합니다. 표시 이름을 같게 바꿔도 합쳐지지 않습니다.")
    raw, issues = prepare(master)
    if raw.empty:
        st.warning("유효한 측정값과 시간 데이터가 없습니다.")
        return
    labels = raw[["profile", "label"]].drop_duplicates().set_index("profile").label.to_dict()
    chosen = st.multiselect("분석 대상 (보고서 전체에 적용)", list(labels), default=list(labels), format_func=labels.get, key="analysis_profiles")
    if not chosen:
        st.info("분석 대상을 선택해 주세요.")
        return
    raw = raw[raw.profile.isin(chosen)].copy()
    summary = summarize(raw)
    organs = sorted(summary.organ.unique())
    times = sorted(summary.timepoint_hour.unique())
    col1, col2, col3 = st.columns(3)
    tumor = col1.selectbox("표적 장기", organs, index=organs.index("Tumor") if "Tumor" in organs else 0)
    normal_options = [o for o in organs if o != tumor]
    if not normal_options:
        st.info("비율과 순위 분석에는 서로 다른 장기가 2개 이상 필요합니다.")
        return
    normal = col2.selectbox("순위·Quadrant 비교 장기", normal_options, index=normal_options.index("Kidney") if "Kidney" in normal_options else 0)
    reference = col3.selectbox("Reference", chosen, format_func=labels.get)
    method = st.selectbox("AUC 계산 방식", list(AUC_METHODS), format_func=AUC_METHODS.get, key="analysis_auc_method")
    c1, c2 = st.columns(2)
    start = c1.number_input("공통 AUC 시작 (h)", min_value=0.0, value=float(times[0]), key="analysis_auc_start")
    end = c2.number_input("공통 AUC 종료 (h)", min_value=0.0, value=float(times[-1]), key="analysis_auc_end")
    st.info("선형 사다리꼴 적분 · 모든 AUC/비율/순위에 동일 구간 적용. 0시간 가정은 실제 0시간 값이 없을 때만 적용됩니다. "
            "0시간부터 적분하려면 시작을 0으로 설정하세요. 관측 범위 내 경계값은 선형 보간하며, 종료 시점 외삽은 하지 않습니다.")
    if end <= start:
        st.warning("AUC 종료 시점은 시작 시점보다 커야 합니다. AUC 결과는 계산 불가로 표시됩니다.")
    aucs = auc_table(summary, method, start, end)
    ratios, auc_ratios = ratio_tables(summary, aucs, tumor)
    early = st.selectbox("유지율 초기 시점 (h)", times, key="retention_early")
    late = st.selectbox("유지율 후기 시점 (h)", times, index=len(times) - 1, key="retention_late")
    retention = retention_table(summary, early, late)
    weight = st.slider("후보 점수: 표적 AUC 가중치 (나머지는 비교 장기 AUC)", 0.0, 1.0, 0.5, 0.05)
    independent = st.checkbox("선택한 후보군과 Reference는 서로 독립된 개체군이며, 투여량·측정 조건·시험 설계를 비교할 수 있습니다.", value=False)
    comparisons = reference_comparison(raw, summary, reference, independent)
    ranking = rank_candidates(aucs, tumor, normal, weight)
    tabs = st.tabs(["Candidate Ranking & Quadrant", "Tumor-to-Organ & AUC ratio", "Retention & Clearance", "Reference 비교", "One-click BioD Report"])
    figures = []
    with tabs[0]:
        st.caption("탐색적 상대 점수: 표적 AUC가 높고 비교 장기 AUC가 낮을수록 높은 백분위 점수. 동점은 같은 순위입니다. "
                   "선택한 후보·가중치에 따라 점수가 달라지며 통계적 유의성을 뜻하지 않습니다.")
        eligible = len(ranking)
        st.write(f"공통 구간 평가 가능 {eligible} / {len(chosen)}개 그룹")
        st.dataframe(ranking.drop(columns="profile"), hide_index=True, use_container_width=True)
        if not ranking.empty:
            refrow = ranking[ranking.profile == reference]
            threshold_options = ["중앙값"] + (["Reference"] if not refrow.empty else [])
            threshold = st.radio("Quadrant 기준선", threshold_options, horizontal=True)
            xcut = float(refrow.normal_auc.iloc[0] if threshold == "Reference" else ranking.normal_auc.median())
            ycut = float(refrow.tumor_auc.iloc[0] if threshold == "Reference" else ranking.tumor_auc.median())
            ranking["quadrant"] = [
                "표적↑ / 비교장기↓" if y >= ycut and x <= xcut else
                "표적↑ / 비교장기↑" if y >= ycut else
                "표적↓ / 비교장기↓" if x <= xcut else "표적↓ / 비교장기↑"
                for x, y in zip(ranking.normal_auc, ranking.tumor_auc)]
            fig = px.scatter(ranking, x="normal_auc", y="tumor_auc", color="quadrant", hover_name="label", hover_data=["score", "rank"],
                             labels={"normal_auc": f"{normal} AUC (%ID/g·h) ↓", "tumor_auc": f"{tumor} AUC (%ID/g·h) ↑"}, title=f"Candidate Quadrant · {start:g}–{end:g} h")
            fig.add_vline(x=xcut, line_dash="dash")
            fig.add_hline(y=ycut, line_dash="dash")
            fig.update_traces(marker_size=14)
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"기준: {threshold} · X={xcut:.4g}, Y={ycut:.4g} · 경계값 포함: 표적↑, 비교장기↓")
            figures.append(fig)
        else:
            st.info("표적·비교 장기의 공통 구간 AUC가 모두 있는 그룹이 없습니다.")
        with st.expander("그룹·장기별 AUC 계산 상태"):
            st.dataframe(aucs.drop(columns="profile"), hide_index=True)
    with tabs[1]:
        st.caption("시점별 비율 = 표적 평균 / 장기 평균. AUC ratio = 동일 구간의 표적 AUC / 장기 AUC. "
                   "두 값은 서로 다른 지표이며 개체별 비율의 평균이 아닙니다. 분모가 0이거나 짝이 없으면 미산출합니다.")
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
        st.caption("유지율 = 후기/초기 × 100, 감소율 = 100 − 유지율 (증가하면 음수). 겉보기 k = ln(초기/후기)/Δt, "
                   "겉보기 반감기 = ln(2)/k. 감소하는 양수 두 점에만 반감기를 계산합니다. 전신 청소율(CL)·말단 소실 반감기를 추정한 값이 아닙니다.")
        st.dataframe(retention.drop(columns="profile"), hide_index=True, use_container_width=True)
    with tabs[3]:
        st.caption("증감률 = (후보 평균/Reference 평균 − 1) × 100. 같은 장기·실측 시점끼리 비교합니다. "
                   "검정: 독립 양측 Welch t-test, q: 현재 선택된 전체 후보×장기×시간의 유효 검정에 Benjamini–Hochberg FDR 보정. "
                   "평균값만 있는 입력·중복 개체·ID 없음은 검정하지 않습니다. AUC/비율에는 이 검정을 적용하지 않습니다.")
        if ttest_ind is None:
            st.warning("SciPy가 없어 검정은 비활성 상태입니다. requirements.txt의 패키지를 설치하면 활성화됩니다.")
        st.dataframe(comparisons.drop(columns="profile"), hide_index=True, use_container_width=True)
        st.markdown("검정 구현 근거: [SciPy Welch t-test 문서](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html)")
    with tabs[4]:
        st.write("현재 분석 설정·요약 통계·순위·비율·유지율·Reference 검정·원자료와 그래프를 ZIP 보고서로 받습니다. HTML은 오프라인 열람·인쇄가 가능하고, Excel에는 모든 결과표가 포함됩니다.")
        st.dataframe(issues, hide_index=True)
        # Include core BioD figures in the portable report as well as decision plots.
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
                        quadrant_threshold=threshold if not ranking.empty else "unavailable",
                        interpretation="Exploratory cohort-relative ranking; no efficacy/safety conclusion")
        tables = dict(Summary=summary, AUC=aucs, Ratios=ratios, AUC_Ratios=auc_ratios,
                      Retention=retention, Reference=comparisons, Ranking=ranking, Quality=issues, Raw_Data=raw)
        digest = hashlib.sha256(pd.util.hash_pandas_object(raw, index=True).values.tobytes() + json.dumps(settings, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        report = _report_download(tables, settings, tuple(fig.to_json() for fig in figures))
        st.download_button("One-click BioD Report 다운로드", data=report, file_name=f"BioD_Report_{digest}.zip", mime="application/zip", key=f"report_{digest}", type="primary")
