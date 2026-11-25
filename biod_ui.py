"""Candidate analysis and a separate portable report view."""
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from biod_analysis import (AUC_METHODS, prepare, summarize, auc_table, ratio_tables,
                           retention_table, reference_comparison, rank_candidates,
                           build_report, excel_bytes, ttest_ind)


@st.cache_data(show_spinner="보고서 준비 중...", max_entries=3)
def _report_download(tables, settings, figure_jsons):
    settings = dict(settings, generated_at=datetime.now(ZoneInfo("Asia/Seoul")).isoformat())
    return build_report(tables, settings, [go.Figure(json.loads(s)) for s in figure_jsons])


def _unavailable(report_tab, message):
    st.info(message)
    with report_tab:
        st.subheader("BioD Report")
        st.info(message)


def _compact(frame, columns, names, short_labels):
    view = frame[columns].copy()
    if "label" in view:
        view["label"] = frame.profile.map(short_labels)
    view = view.rename(columns=names)
    formats = {c: "{:.1f}" if "%" in c else "{:.3f}" for c in view.select_dtypes(include="number")}
    st.dataframe(view.style.format(formats, na_rep="—"), hide_index=True, use_container_width=True)
    return view


def _p_text(value):
    return "—" if pd.isna(value) else f"{value:.3g}"


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
    identities = raw[["profile", "display_group_id"]].drop_duplicates("profile")
    repeated = identities.display_group_id.duplicated(keep=False)
    short_labels = {r.profile: labels[r.profile] if repeated.loc[i] else str(r.display_group_id)
                    for i, r in identities.iterrows()}
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
    with tabs[0]:
        st.caption("표적 장기 AUC는 높고, 비교 장기 AUC는 낮은 정도를 동일하게 반영한 참고 순위입니다.")
        st.write(f"비교 가능 {len(ranking)} / {len(chosen)}개 물질")
        display = ranking[["rank", "label", "tumor_auc", "normal_auc", "auc_ratio"]].rename(columns={
            "rank": "순위", "label": "물질", "tumor_auc": f"{tumor} AUC", "normal_auc": f"{normal} AUC", "auc_ratio": f"{tumor}/{normal} AUC 비율"})
        display["물질"] = ranking.profile.map(short_labels)
        st.dataframe(display, hide_index=True, use_container_width=True)
        if not ranking.empty:
            names = [f"{int(r['rank'])}위 {short_labels[r.profile]}" + (" (Reference)" if r.profile == reference else "")
                     for _, r in ranking.iterrows()]
            colors = ["#E8913A" if p == reference else "#3563B9" for p in ranking.profile]
            fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.12,
                                subplot_titles=[f"{tumor} AUC · 높을수록 좋음", f"{normal} AUC · 낮을수록 좋음"])
            for column, value_column in [(1, "tumor_auc"), (2, "normal_auc")]:
                fig.add_trace(go.Bar(x=ranking[value_column], y=names, orientation="h", marker_color=colors,
                                     text=ranking[value_column], texttemplate="%{x:.2f}", textposition="outside", cliponaxis=False,
                                     hovertemplate="%{y}<br>AUC: %{x:.3f} %ID/g·h<extra></extra>"), row=1, col=column)
            max_auc = float(ranking[["tumor_auc", "normal_auc"]].max().max())
            fig.update_xaxes(title_text="AUC (%ID/g·h)", range=[0, max(1, max_auc * 1.22)])
            fig.update_yaxes(categoryorder="array", categoryarray=names, autorange="reversed", automargin=True)
            fig.update_layout(showlegend=False, height=max(340, 65 * len(ranking) + 100), margin=dict(l=20, r=60, t=65, b=55))
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"같은 행은 같은 물질입니다. 왼쪽은 {tumor} 분포, 오른쪽은 {normal} 분포이며 두 그래프의 AUC 축 범위는 같습니다. 주황색은 Reference입니다.")
            figures.append(fig)
        else:
            st.info("표적·비교 장기의 선택 구간 AUC가 모두 있는 물질이 없습니다.")
        with st.expander("계산 방법 및 AUC 상세"):
            st.caption("표적 AUC의 높은 순위 백분위와 비교 장기 AUC의 낮은 순위 백분위를 1:1로 반영합니다. "
                       "동점은 같은 순위이며, 선택한 물질에 따라 순위가 달라집니다. 통계적 유의성을 뜻하지 않습니다. AUC 단위: %ID/g·h.")
            st.dataframe(aucs.drop(columns="profile"), hide_index=True)
    with tabs[1]:
        r1, r2 = st.columns(2)
        ratio_organ = r1.selectbox("비율을 볼 장기", normal_options, index=normal_options.index(normal), key="ratio_organ_filter")
        ratio_time = r2.selectbox("측정 시점 (h)", times, index=len(times) - 1, key="ratio_time_filter")
        st.markdown(f"#### {tumor}-Organ ratio")
        st.caption(f"{tumor}/{ratio_organ} · {ratio_time:g}h · Mean 단위: %ID/g")
        selected_ratios = ratios[(ratios.organ == ratio_organ) & (ratios.timepoint_hour == ratio_time)]
        ratio_view = _compact(selected_ratios, ["label", "mean", "tumor_mean", "tumor_to_organ"],
                 {"label": "물질", "mean": f"{ratio_organ} Mean", "tumor_mean": f"{tumor} Mean", "tumor_to_organ": f"{tumor}/Organ ratio"}, short_labels)
        export_context = dict(target=tumor, organ=ratio_organ, selected_profiles=[labels[p] for p in chosen],
                              missing_values="Blank = unavailable (missing measurements or non-positive denominator)")
        st.download_button(f"{tumor}-Organ ratio Excel 다운로드",
                           data=excel_bytes({"Organ_Ratio": ratio_view}, dict(export_context, time_h=ratio_time, mean_unit="%ID/g", calculation="Ratio of means")),
                           file_name=f"BioD_Organ_Ratio_{ratio_time:g}h.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="ratio_excel")
        st.markdown(f"#### {tumor}-Organ ratio (AUC)")
        st.caption(f"{start:g}–{end:g}h · AUC 단위: %ID/g·h")
        auc_ratio_view = _compact(auc_ratios[auc_ratios.organ == ratio_organ], ["label", "auc", "tumor_auc", "auc_ratio"],
                 {"label": "물질", "auc": f"{ratio_organ} AUC", "tumor_auc": f"{tumor} AUC", "auc_ratio": f"{tumor}/Organ AUC ratio"}, short_labels)
        st.download_button(f"{tumor}-Organ ratio (AUC) Excel 다운로드",
                           data=excel_bytes({"Organ_AUC_Ratio": auc_ratio_view}, dict(export_context, start_h=start, end_h=end, auc_method=AUC_METHODS[method], auc_unit="%ID/g·h", calculation="Ratio of AUCs")),
                           file_name=f"BioD_Organ_AUC_Ratio_{start:g}-{end:g}h.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="auc_ratio_excel")
        st.caption("비율은 평균값끼리, AUC 비율은 같은 구간의 AUC끼리 나눈 값입니다. 분모 0·측정값 부족은 —로 표시합니다.")
        valid_ratios = ratios[ratios.organ == ratio_organ].dropna(subset=["tumor_to_organ"]).copy()
        if not valid_ratios.empty:
            valid_ratios["label"] = valid_ratios.profile.map(short_labels)
            fig = px.line(valid_ratios.sort_values("timepoint_hour"), x="timepoint_hour", y="tumor_to_organ", color="label", markers=True,
                          title=f"{tumor}/{ratio_organ}", labels={"timepoint_hour": "Time (h)", "tumor_to_organ": "Ratio"})
            st.plotly_chart(fig, use_container_width=True)
            figures.append(fig)
    with tabs[2]:
        c0, c1, c2 = st.columns(3)
        retention_organ = c0.selectbox("유지율을 볼 장기", organs, index=organs.index(tumor), key="retention_organ_filter")
        early = c1.selectbox("초기 시점 (h)", times, key="retention_early")
        late = c2.selectbox("후기 시점 (h)", times, index=len(times) - 1, key="retention_late")
        retention = retention_table(summary, early, late)
        st.caption(f"{retention_organ} · {early:g}h → {late:g}h · 초기값을 100%로 본 변화입니다. 감소율이 음수면 분포가 증가한 것입니다.")
        selected_retention = retention[retention.organ == retention_organ].copy()
        selected_retention["label"] = selected_retention.profile.map(short_labels)
        bars = selected_retention.melt(id_vars=["label"], value_vars=["retention_pct", "decrease_pct"], var_name="지표", value_name="비율 (%)").dropna(subset=["비율 (%)"])
        bars["지표"] = bars["지표"].replace({"retention_pct": "유지율", "decrease_pct": "감소율"})
        if not bars.empty:
            fig = px.bar(bars, x="비율 (%)", y="label", color="지표", barmode="group", orientation="h", text="비율 (%)",
                         color_discrete_map={"유지율": "#3563B9", "감소율": "#E8913A"}, labels={"label": "물질"}, title=f"{retention_organ} 유지율·감소율")
            fig.update_traces(texttemplate="%{x:.1f}%", textposition="outside", cliponaxis=False)
            fig.add_vline(x=100, line_dash="dot", line_color="gray")
            fig.update_layout(height=max(320, 90 * len(selected_retention)), yaxis=dict(autorange="reversed"), margin=dict(r=80))
            st.plotly_chart(fig, use_container_width=True)
            figures.append(fig)
        else:
            st.info("두 시점의 측정값과 초기 양수 값이 있어야 유지율을 계산할 수 있습니다.")
        _compact(selected_retention, ["label", "retention_pct", "decrease_pct"],
                 {"label": "물질", "retention_pct": "유지율 (%)", "decrease_pct": "감소율 (%)"}, short_labels)
        st.caption("유지율 = 후기/초기 × 100 · 감소율 = 100 − 유지율. 초기·후기 Mean과 겉보기 반감기는 보고서에 포함됩니다.")
    with tabs[3]:
        f1, f2 = st.columns(2)
        reference_organ = f1.selectbox("Reference와 비교할 장기", organs, index=organs.index(tumor), key="reference_organ_filter")
        reference_time = f2.selectbox("비교 시점 (h)", times, index=len(times) - 1, key="reference_time_filter")
        with st.expander("통계 검정 설정"):
            independent = st.checkbox("선택한 후보군과 Reference는 서로 독립된 개체군이며, 투여량·측정 조건·시험 설계를 비교할 수 있습니다.", value=False, key="analysis_independent")
        comparisons = reference_comparison(raw, summary, reference, independent)
        st.caption(f"Reference: {short_labels[reference]} · {reference_organ} · {reference_time:g}h · Mean 단위: %ID/g")
        st.caption("p값: 양측 Student t-test (독립 두 군, 등분산 가정). 보정 p값(q): Benjamini–Hochberg FDR. "
                   "보정 범위는 선택한 전체 물질×장기×시간의 유효 검정이며, 장기·시점 표시 필터로 바뀌지 않습니다. 검정 결과는 q<0.05 기준입니다.")
        if ttest_ind is None:
            st.warning("SciPy 설치 후 통계 검정을 사용할 수 있습니다.")
        selected_comparison = comparisons[(comparisons.organ == reference_organ) & (comparisons.timepoint_hour == reference_time)].copy()
        selected_comparison["p_display"] = selected_comparison.p_value.map(_p_text)
        selected_comparison["q_display"] = selected_comparison.q_bh.map(_p_text)
        short_status = {"독립군·시험 조건 비교 가능 여부 확인 필요": "독립군 확인 필요", "평균값 입력: 검정 제외": "개체 원자료 필요"}
        selected_comparison["result"] = selected_comparison.apply(
            lambda r: ("유의한 차이 (q<0.05)" if r.q_bh < 0.05 else "유의한 차이 미확인") if pd.notna(r.q_bh)
            else short_status.get(r.test_status, r.test_status), axis=1) if not selected_comparison.empty else pd.Series(dtype=str)
        if selected_comparison.empty:
            st.info("선택한 장기·시점에 Reference와 비교할 후보 데이터가 없습니다.")
        _compact(selected_comparison, ["label", "mean", "reference_mean", "change_pct", "p_display", "q_display", "result"],
                 {"label": "물질", "mean": "후보 Mean", "reference_mean": "Reference Mean", "change_pct": "증감률 (%)",
                  "p_display": "p값 (Student t-test)", "q_display": "보정 p값 (BH q)", "result": "검정 결과"}, short_labels)
        st.caption("증감률 = (후보/Reference − 1) × 100. 검정을 하지 못한 경우 —와 사유를 표시합니다. 표본 수와 검정 상세는 보고서에서 확인할 수 있습니다.")

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
                        ratio_organ=ratio_organ, ratio_time_h=ratio_time, retention_organ=retention_organ,
                        reference_view_organ=reference_organ, reference_view_time_h=reference_time,
                        independent_groups_confirmed=independent, selected_profiles=[labels[p] for p in chosen],
                        statistics="Two-sided Student t-test (equal variance); BH FDR over all valid selected comparisons",
                        ratios="Ratio of group means; ratio of AUCs on fixed common interval",
                        retention="Two-timepoint apparent decline; not systemic CL or terminal half-life",
                        summary_input="rows counts input records, not necessarily animals; SD omitted for summary inputs",
                        candidate_chart="Paired horizontal AUC bars; shared scale; Reference highlighted",
                        interpretation="Exploratory cohort-relative ranking; equal weight for target and comparator")
        tables = dict(Summary=summary, AUC=aucs, Ratios=ratios, AUC_Ratios=auc_ratios,
                      Retention=retention, Reference=comparisons, Ranking=ranking, Quality=issues, Raw_Data=raw)
        digest = hashlib.sha256(pd.util.hash_pandas_object(raw, index=True).values.tobytes() + json.dumps(settings, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        report = _report_download(tables, settings, tuple(fig.to_json() for fig in figures))
        st.download_button("One-click BioD Report 다운로드", data=report, file_name=f"BioD_Report_{digest}.zip", mime="application/zip", key=f"report_{digest}", type="primary")
        with st.expander("보고서 포함 항목 및 데이터 확인"):
            st.write("평균·AUC, 후보 순위·물질별 AUC 비교 그래프, 장기 비율, 유지율·감소율, Reference 비교, 분석에 사용한 표준화 원자료")
            st.dataframe(issues, hide_index=True)
