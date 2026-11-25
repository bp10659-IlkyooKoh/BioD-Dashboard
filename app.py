import streamlit as st
import pandas as pd
import numpy as np
import re
import plotly.express as px
import plotly.graph_objects as go
import io
import hashlib
import zipfile
from pathlib import Path
from biod_analysis import integrate_curve
from biod_ui import render_analysis
from biod_mollim import parse_mollim_workbook
from biod_labels import clean_group_with_tp

# =====================================================
# 페이지 설정
# =====================================================
st.set_page_config(
    page_title="RPT Preclinical Center BioD Dashboard v2.0",
    page_icon="🧪",
    layout="wide"
)

# =====================================================
# SK Theme UI / UX CSS
# =====================================================
st.markdown("""
<style>
    :root {
        --sk-red: #E0002A;
        --sk-orange: #FF7A00;
        --sk-yellow: #FDB913;
        --sk-navy: #1F2937;
        --sk-dark: #111827;
        --sk-bg: #FFF7F0;
        --sk-card: #FFFFFF;
        --sk-soft-red: #FFF1F2;
        --sk-soft-orange: #FFF7ED;
        --sk-border: rgba(224, 0, 42, 0.18);
        --sk-shadow: rgba(17, 24, 39, 0.10);
    }

    .stApp {
        background:
            radial-gradient(circle at top left, rgba(255, 122, 0, 0.16), transparent 34%),
            radial-gradient(circle at top right, rgba(224, 0, 42, 0.12), transparent 30%),
            linear-gradient(180deg, #FFF7F0 0%, #FFFDF9 46%, #F8FAFC 100%);
    }

    .block-container {
        padding-top: 1.7rem;
        padding-bottom: 3rem;
        max-width: 1500px;
    }

    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #3A0A0F 0%, #5A1118 45%, #111827 100%);
        border-right: 1px solid rgba(255, 255, 255, 0.10);
    }

    section[data-testid="stSidebar"] * {
        color: #F9FAFB;
    }

    section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] p,
    section[data-testid="stSidebar"] li {
        color: #FFE4D6;
        line-height: 1.55;
    }

    /* Hero */
    .hero-card {
        background:
            linear-gradient(135deg, rgba(224, 0, 42, 0.96) 0%, rgba(255, 122, 0, 0.94) 58%, rgba(253, 185, 19, 0.88) 100%);
        padding: 34px 38px;
        border-radius: 28px;
        color: white;
        box-shadow: 0 24px 54px rgba(224, 0, 42, 0.26);
        margin-bottom: 24px;
        border: 1px solid rgba(255, 255, 255, 0.25);
    }

    .hero-kicker {
        display: inline-block;
        padding: 6px 12px;
        border-radius: 999px;
        background: rgba(17, 24, 39, 0.24);
        border: 1px solid rgba(255, 255, 255, 0.24);
        font-size: 0.82rem;
        font-weight: 800;
        letter-spacing: 0.03em;
        margin-bottom: 12px;
    }

    .hero-title {
        font-size: 2.35rem;
        font-weight: 900;
        letter-spacing: -0.055em;
        margin-bottom: 10px;
        line-height: 1.12;
    }

    .hero-subtitle {
        font-size: 1.04rem;
        line-height: 1.68;
        opacity: 0.97;
        max-width: 980px;
        font-weight: 520;
    }

    .hero-badges {
        margin-top: 18px;
    }

    .badge {
        display: inline-block;
        padding: 8px 13px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.20);
        border: 1px solid rgba(255, 255, 255, 0.34);
        color: white;
        font-size: 0.84rem;
        font-weight: 800;
        margin-right: 8px;
        margin-bottom: 8px;
    }

    /* Cards */
    .soft-card {
        background: rgba(255, 255, 255, 0.96);
        border: 1px solid var(--sk-border);
        border-radius: 24px;
        padding: 24px 26px;
        box-shadow: 0 14px 34px var(--sk-shadow);
        margin-bottom: 20px;
    }

    .section-title {
        font-size: 1.28rem;
        font-weight: 900;
        color: #111827;
        margin-bottom: 6px;
        letter-spacing: -0.035em;
    }

    .section-caption {
        font-size: 0.94rem;
        color: #6B7280;
        line-height: 1.6;
        margin-bottom: 14px;
    }

    .section-label {
        display: inline-block;
        color: var(--sk-red);
        background: var(--sk-soft-red);
        border: 1px solid rgba(224, 0, 42, 0.18);
        border-radius: 999px;
        padding: 5px 10px;
        font-size: 0.78rem;
        font-weight: 850;
        margin-bottom: 9px;
    }

    /* KPI */
    .metric-card {
        background: linear-gradient(180deg, #FFFFFF 0%, #FFF7ED 100%);
        border: 1px solid rgba(255, 122, 0, 0.22);
        border-radius: 22px;
        padding: 19px 18px;
        box-shadow: 0 12px 30px rgba(255, 122, 0, 0.10);
        min-height: 122px;
        position: relative;
        overflow: hidden;
    }

    .metric-card:before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        width: 7px;
        height: 100%;
        background: linear-gradient(180deg, var(--sk-red), var(--sk-orange));
    }

    .metric-label {
        color: #6B7280;
        font-size: 0.86rem;
        font-weight: 850;
        margin-bottom: 8px;
        padding-left: 6px;
    }

    .metric-value {
        color: #111827;
        font-size: 2.02rem;
        font-weight: 950;
        line-height: 1.05;
        letter-spacing: -0.055em;
        padding-left: 6px;
    }

    .metric-caption {
        color: #9CA3AF;
        font-size: 0.78rem;
        margin-top: 8px;
        padding-left: 6px;
    }

    .hint-box {
        background: #FFF7ED;
        border: 1px solid rgba(255, 122, 0, 0.28);
        color: #7C2D12;
        padding: 14px 16px;
        border-radius: 18px;
        font-size: 0.92rem;
        line-height: 1.58;
        margin-bottom: 14px;
    }

    .success-box {
        background: #FFF1F2;
        border: 1px solid rgba(224, 0, 42, 0.24);
        color: #7F1D1D;
        padding: 14px 16px;
        border-radius: 18px;
        font-size: 0.92rem;
        line-height: 1.58;
        margin: 18px 0;
        font-weight: 650;
    }

    /* File uploader */
    div[data-testid="stFileUploader"] {
        background: linear-gradient(180deg, #FFFFFF 0%, #FFF7ED 100%);
        border: 2px dashed rgba(224, 0, 42, 0.34);
        border-radius: 22px;
        padding: 18px;
    }

    div[data-testid="stFileUploader"] button {
        background: linear-gradient(135deg, var(--sk-red), var(--sk-orange)) !important;
        color: white !important;
        border-radius: 14px !important;
        border: none !important;
        font-weight: 850 !important;
    }

    /* Widgets */
    .stMultiSelect [data-baseweb="select"] {
        border-radius: 15px;
        border-color: rgba(224, 0, 42, 0.22);
    }

    div[data-testid="stDataFrame"] {
        border-radius: 18px;
        overflow: hidden;
        border: 1px solid rgba(224, 0, 42, 0.14);
        box-shadow: 0 8px 22px rgba(17, 24, 39, 0.045);
    }

    .stDownloadButton button {
        border-radius: 15px !important;
        font-weight: 850 !important;
        border: none !important;
        background: linear-gradient(135deg, var(--sk-red), var(--sk-orange)) !important;
        color: white !important;
        padding: 0.68rem 1.1rem !important;
        box-shadow: 0 12px 24px rgba(224, 0, 42, 0.20);
    }

    .stButton button {
        border-radius: 15px !important;
    }

    /* Toggle */
    div[data-testid="stToggle"] label {
        font-weight: 760;
        color: #374151;
    }

    /* Tabs */
    button[data-baseweb="tab"] {
        background: rgba(255, 255, 255, 0.92);
        border-radius: 18px 18px 0 0;
        margin-right: 6px;
        padding: 13px 18px;
        font-weight: 850;
        border: 1px solid rgba(224, 0, 42, 0.10);
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        color: var(--sk-red);
        border-bottom: 4px solid var(--sk-orange);
        background: #FFFFFF;
    }

    /* Expander */
    details {
        border-radius: 18px !important;
    }

    hr {
        margin-top: 1.15rem;
        margin-bottom: 1.15rem;
    }
</style>
""", unsafe_allow_html=True)


# =====================================================
# UI 헬퍼 함수
# =====================================================
def render_metric_card(label, value, caption=""):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-caption">{caption}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_section_header(title, caption="", label="ANALYSIS"):
    st.markdown(
        f"""
        <div class="section-label">{label}</div>
        <div class="section-title">{title}</div>
        <div class="section-caption">{caption}</div>
        """,
        unsafe_allow_html=True
    )


# =====================================================
# 사이드바
# =====================================================
with st.sidebar:
    st.markdown("# 🧪 BioD Dashboard")
    st.markdown("### RPT Preclinical Center")
    st.markdown("---")
    st.markdown("#### Workflow")
    st.markdown("""
    1. Raw Excel 업로드  
    2. CRO 자동 인식  
    3. %ID/g 표준화  
    4. 그룹명 매핑  
    5. Mean / Bar / PK / AUC 확인
    """)
    st.markdown("---")
    st.markdown("#### 지원 CRO")
    st.markdown("""
    - 몰림  
    - Minerva  
    - KIRAMS  
    """)
    st.markdown("---")
    st.markdown("#### 추가기능 지속 업데이트 예정")


# =====================================================
# Hero
# =====================================================
st.markdown("""
<div class="hero-card">
    <div class="hero-kicker">SK BioD Analytics Prototype</div>
    <div class="hero-title">🧪 Biodistribution Data Dashboard</div>
    <div class="hero-subtitle">
        Molim, Minerva, KIRAMS raw Excel 데이터를 하나의 분석 포맷으로 통합하고,
        Mean Table, Whole BioD 비교, PK Trend, AUC 계산까지 한 화면에서 확인합니다.
    </div>
    <div class="hero-badges">
        <span class="badge">Molim</span>
        <span class="badge">Minerva</span>
        <span class="badge">KIRAMS Graph Parser</span>
        <span class="badge">%ID/g Mean ± SD</span>
        <span class="badge">AUC_0-last</span>
        <span class="badge">Excel Export</span>
    </div>
</div>
""", unsafe_allow_html=True)


# =====================================================
# 공통 유틸리티 함수
# =====================================================
def clean(x):
    if pd.isna(x):
        return ""
    return str(x).strip()


def clean_text(x):
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass

    s = str(x).replace("\n", " ").replace("\r", " ").replace("\t", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def to_float(x):
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
    except Exception:
        pass

    if isinstance(x, (int, float, np.integer, np.floating)):
        return float(x)

    s = clean_text(x).replace(",", "")
    if s == "":
        return None

    try:
        return float(s)
    except Exception:
        return None


def extract_hour(tp):
    s = clean(tp).lower().strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        return float(s)  # Unitless numeric time is interpreted as hours.
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|d|day|days|w|wk|week|weeks|min|mins|minute|minutes)", s)
    if not match:
        return np.nan
    value, unit = float(match.group(1)), match.group(2)
    factor = 1 / 60 if unit.startswith("min") else 24 if unit.startswith("d") else 168 if unit.startswith("w") else 1
    return value * factor


def parse_time_point(tp):
    s = clean_text(tp).lower()
    if not s:
        return None, None

    m = re.search(
        r"(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|d|day|days|w|wk|week|weeks)\b",
        s
    )

    if m:
        num = float(m.group(1))
        unit = m.group(2)

        if unit in ["h", "hr", "hrs", "hour", "hours"]:
            unit = "h"
        elif unit in ["d", "day", "days"]:
            unit = "d"
        else:
            unit = "w"

        return num, unit

    m = re.search(
        r"(\d+(?:\.\d+)?)(h|hr|hrs|d|day|days|w|wk|week|weeks)\b",
        s
    )

    if m:
        num = float(m.group(1))
        unit = m.group(2)

        if unit in ["h", "hr", "hrs"]:
            unit = "h"
        elif unit in ["d", "day", "days"]:
            unit = "d"
        else:
            unit = "w"

        return num, unit

    return None, None


def format_timepoint(tp_num, tp_unit, fallback=""):
    if tp_num is not None and tp_unit:
        if float(tp_num).is_integer():
            return f"{int(tp_num)}{tp_unit}"
        return f"{tp_num}{tp_unit}"

    return clean_text(fallback)


def standardize_timepoint(tp):
    if pd.isna(tp) or str(tp).strip().lower() == "nan":
        return "Unknown"

    return str(tp).strip().lower().replace(" ", "")


def find_column(df, candidates):
    cols_map = {}

    for col in df.columns:
        key = (
            str(col)
            .strip()
            .lower()
            .replace(" ", "")
            .replace("_", "")
            .replace("\n", "")
            .replace("\r", "")
            .replace("-", "")
            .replace("/", "")
            .replace(".", "")
            .replace("(", "")
            .replace(")", "")
        )
        cols_map[key] = col

    for cand in candidates:
        cand_key = (
            str(cand)
            .strip()
            .lower()
            .replace(" ", "")
            .replace("_", "")
            .replace("\n", "")
            .replace("\r", "")
            .replace("-", "")
            .replace("/", "")
            .replace(".", "")
            .replace("(", "")
            .replace(")", "")
        )

        if cand_key in cols_map:
            return cols_map[cand_key]

        for key, original in cols_map.items():
            if cand_key in key or key in cand_key:
                return original

    return None


def get_uploaded_file_name(file):
    return getattr(file, "name", str(file))


def reset_file_pointer(file):
    try:
        file.seek(0)
    except Exception:
        pass


def normalize_organ(v):
    s = clean_text(v)

    if not s:
        return ""

    key = s.lower().strip()

    organ_alias = {
        "blood": "Blood",
        "heart": "Heart",
        "liver": "Liver",
        "lung": "Lung",
        "lungs": "Lung",
        "spleen": "Spleen",
        "kidney": "Kidney",
        "kidneys": "Kidney",
        "stomach": "Stomach",
        "small intestine": "Small intestine",
        "large intestine": "Large intestine",
        "muscle": "Muscle",
        "tibia": "Tibia",
        "brain": "Brain",
        "tumor": "Tumor",
        "tumour": "Tumor",
        "tail": "Tail",
        "femur": "Femur",
    }

    return organ_alias.get(key, s[:1].upper() + s[1:])


def is_organ_token(v):
    s = clean_text(v).lower().strip()

    if not s:
        return False

    organ_set = {
        "blood", "heart", "liver", "lung", "lungs", "spleen", "kidney", "kidneys",
        "stomach", "small intestine", "large intestine", "muscle", "tibia",
        "brain", "tumor", "tumour", "tail", "femur"
    }

    return s in organ_set


def find_first_group_token(texts):
    for t in texts:
        m = re.search(r"#\d+", t)
        if m:
            return m.group(0)

    return None


def find_time_token(texts):
    for t in texts:
        if not t:
            continue

        m = re.search(
            r"\d+(?:\.\d+)?\s*(h|hr|hrs|hour|hours|d|day|days|w|wk|week|weeks)\b",
            t.lower()
        )

        if m:
            return parse_time_point(m.group(0))

    return None, None


# =====================================================
# CRO 자동 인식
# =====================================================
def detect_cro(file, xls):
    file_name = get_uploaded_file_name(file).lower()
    sheets = [str(s).lower() for s in xls.sheet_names]

    if (
        "kirams" in file_name
        or "키람스" in file_name
        or "공동연구" in file_name
        or "biod results analysis" in file_name
    ):
        return "KIRAMS"

    if "minerva" in file_name:
        return "Minerva"

    if (
        any("조직분포결과" in s for s in sheets)
        or any("군분리" in s for s in sheets)
        or any("injection" in s for s in sheets)
        or any("tissue weight" in s for s in sheets)
        or any(s.startswith("#") for s in sheets)
    ):
        return "KIRAMS"

    if any("ex vivo" in s for s in sheets):
        return "Minerva"

    return "몰림"


# =====================================================
# 몰림 파서
# =====================================================
def parse_mollim(file):
    out = parse_mollim_workbook(file, extract_hour)
    for diagnostic in out.attrs.get("parse_diagnostics", []):
        if diagnostic["status"] != "ok":
            st.warning(f"{get_uploaded_file_name(file)} / {diagnostic['sheet']}: {diagnostic['status']}")
    return out


# =====================================================
# Minerva 파서
# =====================================================
def normalize_minerva_group_name(x):
    """
    Minerva Group 명 정리 함수

    예시:
    - "A - SKL37321 - 1h"  -> "SKL37321"
    - "D - SKL37321 - 4h"  -> "SKL37321"
    - "E - SKL37321 - 8h"  -> "SKL37321"
    - "SKL37321"           -> "SKL37321"

    이유:
    - Minerva Group 컬럼에는 cohort letter와 timepoint가 같이 들어갈 수 있음
    - 대시보드에서는 실제 물질명 기준으로 timepoint를 묶어야 함
    """
    s = clean_text(x)

    if s == "" or s.lower() == "nan":
        return "Unknown"

    # 뒤쪽 timepoint 제거: " - 1h", " - 4h", " - 8h", " - 24h" 등
    s = re.sub(
        r"\s*[-_/]\s*\d+\.?\d*\s*(h|hr|hrs|hour|hours|d|day|days|w|wk|week|weeks)\s*$",
        "",
        s,
        flags=re.IGNORECASE
    )

    # 괄호 안 timepoint 제거: "(1h)", "[4h]" 등
    s = re.sub(
        r"\s*[\(\[]\s*\d+\.?\d*\s*(h|hr|hrs|hour|hours|d|day|days|w|wk|week|weeks)\s*[\)\]]\s*$",
        "",
        s,
        flags=re.IGNORECASE
    )

    # 앞쪽 cohort letter 제거: "A - SKL37321" -> "SKL37321"
    # 단, 맨 앞이 알파벳 1글자이고 뒤에 하이픈이 있는 경우만 제거
    m = re.match(r"^\s*[A-Za-z]\s*[-_/]\s*(.+?)\s*$", s)

    if m:
        s = m.group(1).strip()

    return s if s else "Unknown"


def find_minerva_pidg_column(df):
    """
    Minerva %ID/g 컬럼 선택 전용 함수

    우선순위:
    1. Uptake (%ID/g) - Tail corrected
    2. Tail corrected + %ID/g 계열
    3. TC uptake %ID/g 계열
    4. 일반 Uptake (%ID/g)
    5. 기타 %ID/g / ID/g 컬럼

    새 Minerva 파일에는 일반 Uptake와 Tail corrected가 동시에 존재하므로,
    반드시 Tail corrected 값을 우선 사용해야 함.
    """
    columns = list(df.columns)

    def norm(x):
        return (
            str(x)
            .strip()
            .lower()
            .replace(" ", "")
            .replace("_", "")
            .replace("\n", "")
            .replace("\r", "")
            .replace("-", "")
            .replace("/", "")
            .replace(".", "")
            .replace("(", "")
            .replace(")", "")
        )

    normalized = [(col, norm(col)) for col in columns]

    # 1순위: Tail corrected + uptake + id/g
    for col, key in normalized:
        has_uptake = "uptake" in key
        has_idg = "%idg" in key or "idg" in key
        has_tail = "tail" in key
        has_corrected = "corrected" in key or "correct" in key

        if has_uptake and has_idg and has_tail and has_corrected:
            return col

    # 2순위: tail corrected + id/g
    for col, key in normalized:
        has_idg = "%idg" in key or "idg" in key
        has_tail = "tail" in key
        has_corrected = "corrected" in key or "correct" in key

        if has_idg and has_tail and has_corrected:
            return col

    # 3순위: TC uptake %ID/g
    for col, key in normalized:
        has_tc = key.startswith("tc") or "tcuptake" in key
        has_uptake = "uptake" in key
        has_idg = "%idg" in key or "idg" in key

        if has_tc and has_uptake and has_idg:
            return col

    # 4순위: 일반 Uptake (%ID/g)
    for col, key in normalized:
        has_uptake = "uptake" in key
        has_idg = "%idg" in key or "idg" in key
        has_organ = "organ" in key

        if has_uptake and has_idg and not has_organ:
            return col

    # 5순위: fallback
    return find_column(
        df,
        [
            "%id/g",
            "id/g"
        ]
    )


def parse_minerva(file):
    """
    Minerva 포맷 분석 함수

    핵심 수정:
    - group_id는 실제 군/물질 정보인 Group 계열 컬럼을 우선 사용
    - Animal Group Alias(A01, A02 등)는 동물/개체 alias로 취급
    - %ID/g는 Tail corrected 컬럼을 최우선 사용
    - "A - SKL37321 - 1h" 같은 group명은 "SKL37321"로 정리
    """
    reset_file_pointer(file)
    xls = pd.ExcelFile(file)

    target = None

    # TC ex vivo 시트를 우선 선택
    for sheet in xls.sheet_names:
        sheet_lower = str(sheet).lower()
        if "tc" in sheet_lower and "ex vivo" in sheet_lower:
            target = sheet
            break

    # 없으면 일반 ex vivo 시트 선택
    if target is None:
        for sheet in xls.sheet_names:
            sheet_lower = str(sheet).lower()
            if "ex vivo" in sheet_lower:
                target = sheet
                break

    if target is None:
        return pd.DataFrame()

    reset_file_pointer(file)
    df = pd.read_excel(file, sheet_name=target)

    time_col = find_column(df, ["timepoint", "time"])
    organ_col = find_column(df, ["organ", "tissue"])

    # Tail corrected %ID/g 최우선 사용
    pidg_col = find_minerva_pidg_column(df)

    # animal_id는 개체 ID / alias 쪽을 우선 사용
    animal_col = find_column(
        df,
        [
            "animalid",
            "animal id",
            "animal no",
            "animal",
            "mouse",
            "animal group alias"
        ]
    )

    # group_id는 실제 군/물질 컬럼을 우선 사용
    group_col = find_column(
        df,
        [
            "group",
            "compound",
            "treatment group",
            "dose group",
            "test article",
            "material",
            "drug",
            "animal group"
        ]
    )

    if time_col is None or organ_col is None or pidg_col is None:
        return pd.DataFrame()

    temp = pd.DataFrame()

    if group_col is not None:
        temp["group_id"] = df[group_col].apply(normalize_minerva_group_name)
    else:
        temp["group_id"] = "Unknown"

    if animal_col is not None:
        temp["animal_id"] = df[animal_col].fillna("").astype(str)
    else:
        temp["animal_id"] = ""

    temp["timepoint"] = df[time_col].astype(str).fillna("Unknown")
    temp["timepoint_hour"] = temp["timepoint"].apply(extract_hour)
    temp["organ"] = df[organ_col].astype(str).str.strip().str.upper().fillna("Unknown")
    temp["percent_id_per_g"] = pd.to_numeric(df[pidg_col], errors="coerce")

    return temp


def parse_graph_segment(seg_df, file, sheet_name, col_offset=0, segment_name="segment"):
    current_group = None
    current_time_num = None
    current_time_unit = None
    current_org_cols = []
    current_org_names = []

    records = []

    file_name = get_uploaded_file_name(file)
    study_id = Path(file_name).stem

    for r in range(len(seg_df)):
        row = seg_df.iloc[r].tolist()
        texts = [clean_text(v) for v in row]

        g = find_first_group_token(texts)
        if g:
            current_group = g

        tp_num, tp_unit = find_time_token(texts)
        if tp_num is not None:
            current_time_num = tp_num
            current_time_unit = tp_unit

        org_cols = []
        org_names = []

        for c, t in enumerate(texts):
            if is_organ_token(t):
                org_cols.append(col_offset + c)
                org_names.append(normalize_organ(t))

        if len(org_cols) >= 5:
            current_org_cols = org_cols
            current_org_names = org_names
            continue

        if any(t.lower() == "mean" for t in texts if t):
            if not current_group or not current_org_cols or not current_org_names:
                continue

            for abs_col, organ in zip(current_org_cols, current_org_names):
                local_col = abs_col - col_offset

                if local_col < 0 or local_col >= len(row):
                    continue

                val = to_float(row[local_col])

                if val is None:
                    continue

                records.append({
                    "study_id": study_id,
                    "cro_name": "KIRAMS",
                    "source_file": file_name,
                    "source_sheet": sheet_name,
                    "segment": segment_name,
                    "group_id": current_group,
                    "group_label": current_group,
                    "timepoint": format_timepoint(current_time_num, current_time_unit),
                    "timepoint_hour": current_time_num if current_time_num is not None else np.nan,
                    "timepoint_unit": current_time_unit if current_time_unit is not None else "",
                    "organ": organ,
                    "percent_id_per_g": val,
                    "row_type": "mean",
                })

    out = pd.DataFrame(records)

    if not out.empty:
        out["group_id"] = out["group_id"].fillna("Unknown").astype(str)
        out["group_label"] = out["group_label"].fillna("Unknown").astype(str)
        out["organ"] = out["organ"].fillna("Unknown").astype(str)
        out["timepoint"] = out["timepoint"].fillna("").astype(str)
        out["timepoint_hour"] = pd.to_numeric(out["timepoint_hour"], errors="coerce").fillna(0)

    return out


def parse_kirams_graph_sheet(file, sheet_name="graph"):
    reset_file_pointer(file)
    raw = pd.read_excel(file, sheet_name=sheet_name, header=None)
    raw = raw.where(pd.notna(raw), None)

    left_seg = raw.iloc[:, :18].copy() if raw.shape[1] >= 18 else raw.copy()
    right_seg = raw.iloc[:, 20:].copy() if raw.shape[1] > 20 else pd.DataFrame()

    left_df = parse_graph_segment(
        left_seg,
        file=file,
        sheet_name=sheet_name,
        col_offset=0,
        segment_name="left"
    )

    right_df = pd.DataFrame()

    if not right_seg.empty:
        right_df = parse_graph_segment(
            right_seg,
            file=file,
            sheet_name=sheet_name,
            col_offset=20,
            segment_name="right"
        )

    out = pd.concat([left_df, right_df], ignore_index=True, sort=False)

    if not out.empty:
        out = out.drop_duplicates(
            subset=["source_file", "source_sheet", "segment", "group_id", "timepoint", "organ", "percent_id_per_g"]
        ).reset_index(drop=True)

    return out


def parse_kirams(file):
    reset_file_pointer(file)
    xls = pd.ExcelFile(file)

    graph_sheet = None

    for sheet in xls.sheet_names:
        if str(sheet).strip().lower() == "graph":
            graph_sheet = sheet
            break

    if graph_sheet is None:
        for sheet in xls.sheet_names:
            if "graph" in str(sheet).strip().lower():
                graph_sheet = sheet
                break

    if graph_sheet is None:
        st.warning(f"🚨 [KIRAMS 디버그] '{get_uploaded_file_name(file)}'에서 graph 시트를 찾지 못했습니다.")
        return pd.DataFrame()

    try:
        kirams_df = parse_kirams_graph_sheet(file, sheet_name=graph_sheet)
    except Exception as e:
        st.warning(f"🚨 [KIRAMS 디버그] '{get_uploaded_file_name(file)}' graph 시트 파싱 실패: {e}")
        return pd.DataFrame()

    if kirams_df.empty:
        st.warning(f"🚨 [KIRAMS 디버그] '{get_uploaded_file_name(file)}'에서 KIRAMS %ID/g 데이터를 추출하지 못했습니다.")
        return pd.DataFrame()

    out = pd.DataFrame()
    out["group_id"] = kirams_df["group_id"].astype(str)
    out["timepoint"] = kirams_df["timepoint"].astype(str)
    out["timepoint_hour"] = pd.to_numeric(kirams_df["timepoint_hour"], errors="coerce").fillna(0)
    out["animal_id"] = ""
    out["organ"] = kirams_df["organ"].astype(str).str.strip().str.upper()
    out["percent_id_per_g"] = pd.to_numeric(kirams_df["percent_id_per_g"], errors="coerce")

    return out


# =====================================================
# 파일 업로드 및 데이터 로드
# =====================================================
st.markdown('<div class="soft-card">', unsafe_allow_html=True)
render_section_header(
    "📤 BioD 파일 업로드",
    "몰림, Minerva, KIRAMS Excel 파일을 여러 개 동시에 업로드할 수 있습니다.",
    label="STEP 01"
)

uploaded_files = st.file_uploader(
    "BioD 엑셀 파일을 드래그 앤 드롭 하세요.",
    type=["xlsx"],
    accept_multiple_files=True,
    label_visibility="collapsed"
)

st.markdown(
    """
    <div class="hint-box">
    <b>Tip.</b> KIRAMS 파일은 파일명과 시트 구조를 기준으로 자동 인식하며,
    <b>graph 시트의 %ID/g mean 값</b>을 대시보드 입력값으로 사용합니다.
    </div>
    """,
    unsafe_allow_html=True
)
st.markdown('</div>', unsafe_allow_html=True)

if not uploaded_files:
    st.info("파일을 업로드하시면 대시보드가 자동으로 활성화됩니다.")
    st.stop()


all_data = []
overview = []
seen_uploads = set()

with st.spinner("업로드된 BioD 파일을 읽고 표준화하는 중입니다..."):
    for file in uploaded_files:
        try:
            file_digest = hashlib.sha256(file.getvalue()).hexdigest()
            if file_digest in seen_uploads:
                st.warning(f"{get_uploaded_file_name(file)}: 동일한 내용의 파일이 이미 업로드되어 중복 입력을 제외했습니다.")
                continue
            reset_file_pointer(file)
            xls = pd.ExcelFile(file)

            cro = detect_cro(file, xls)

            if cro == "몰림":
                df = parse_mollim(file)
            elif cro == "Minerva":
                df = parse_minerva(file)
            elif cro == "KIRAMS":
                df = parse_kirams(file)
            else:
                continue

            if len(df) == 0:
                st.warning(f"{get_uploaded_file_name(file)}: 인식된 데이터가 없습니다. 물질명·시간·장기·%ID/g 열을 확인해 주세요.")
                continue

            df["source_cro"] = cro
            df["source_file"] = get_uploaded_file_name(file)
            df["source_id"] = file_digest
            df["row_type"] = "mean" if cro == "KIRAMS" else "raw"
            # Recompute from labels so KIRAMS day/week values are in hours too.
            df["timepoint_hour"] = df["timepoint"].apply(extract_hour)

            all_data.append(df)
            seen_uploads.add(file_digest)

            overview.append({
                "File": get_uploaded_file_name(file),
                "CRO": cro,
                "물질명 컬럼": ", ".join(sorted(df["compound_column"].unique())) if "compound_column" in df else "CRO 전용 파서",
                "Groups/Compounds": df["group_id"].nunique(),
                "Animals": df["animal_id"].nunique(),
                "Organs": df["organ"].nunique(),
                "Timepoints": df["timepoint"].nunique()
            })

        except zipfile.BadZipFile:
            st.warning(f"{get_uploaded_file_name(file)}: 확장자는 .xlsx이지만 일반 Excel 파일 형식으로 읽을 수 없습니다. Excel에서 표준 .xlsx로 저장한 사본을 사용해 주세요.")
        except Exception as e:
            st.warning(f"{get_uploaded_file_name(file)} : {e}")

if len(all_data) == 0:
    st.error("데이터를 정상적으로 읽어오지 못했습니다.")
    st.stop()


# =====================================================
# 데이터 전역 세척
# =====================================================
master = pd.concat(all_data, ignore_index=True)
# Preserve invalid records for the v2 quality report; legacy charts use valid values.
analysis_input = master.copy()
master = master.dropna(subset=["percent_id_per_g", "timepoint_hour"])
if master.empty:
    st.error("유효한 측정값과 시간점이 없습니다. 파일의 시간 단위와 %ID/g 값을 확인해 주세요.")
    st.stop()

master["source_cro"] = master["source_cro"].fillna("Unknown")
master["organ"] = master["organ"].fillna("Unknown")
master["timepoint"] = master["timepoint"].apply(standardize_timepoint)

master["group_id"] = master.apply(clean_group_with_tp, axis=1)
master["display_group_id"] = "[" + master["source_cro"].astype(str) + "] " + master["group_id"].astype(str)


# =====================================================
# KPI 요약
# =====================================================
st.markdown(
    '<div class="success-box">✅ 데이터 로딩 완료. 그룹명 매핑 후 Mean Table, Bar Plot, PK Trend를 확인하세요.</div>',
    unsafe_allow_html=True
)

kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)

with kpi_col1:
    render_metric_card("Files", f"{len(uploaded_files):,}", "업로드 파일 수")
with kpi_col2:
    render_metric_card("CRO", f"{master['source_cro'].nunique():,}", "인식된 업체 수")
with kpi_col3:
    render_metric_card("Groups", f"{master['display_group_id'].nunique():,}", "그룹/물질 수")
with kpi_col4:
    render_metric_card("Organs", f"{master['organ'].nunique():,}", "장기 수")
with kpi_col5:
    render_metric_card("Records", f"{len(master):,}", "분석 행 수")


with st.expander("📁 업로드 파일 요약 보기", expanded=True):
    st.dataframe(pd.DataFrame(overview), use_container_width=True, hide_index=True)


# =====================================================
# 기밀 물질명 매핑
# =====================================================
st.markdown('<div class="soft-card">', unsafe_allow_html=True)
render_section_header(
    "✏️ 기밀 물질명 복원",
    "CRO 익명화 그룹명(A, B, C, #302 등)을 실제 물질명으로 수정하면 모든 탭에 자동 반영됩니다.",
    label="STEP 02"
)

unique_display_groups = sorted(master["display_group_id"].unique())
mapping_df = pd.DataFrame({
    "Original Name": unique_display_groups,
    "New Name": unique_display_groups
})

edited_mapping = st.data_editor(
    mapping_df,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Original Name": st.column_config.Column("원래 이름", disabled=True),
        "New Name": st.column_config.TextColumn("표시할 이름", required=True)
    }
)

mapping_dict = dict(zip(edited_mapping["Original Name"], edited_mapping["New Name"]))
master["display_group_id"] = master["display_group_id"].map(mapping_dict).fillna(master["display_group_id"])
analysis_input["timepoint"] = analysis_input["timepoint"].apply(standardize_timepoint)
analysis_input["group_id"] = analysis_input.apply(clean_group_with_tp, axis=1)
analysis_input["display_group_id"] = "[" + analysis_input["source_cro"].astype(str) + "] " + analysis_input["group_id"].astype(str)
analysis_input["display_group_id"] = analysis_input["display_group_id"].map(mapping_dict).fillna(analysis_input["display_group_id"])
st.markdown('</div>', unsafe_allow_html=True)


# =====================================================
# Plotly 스타일
# =====================================================
plotly_config = {
    "toImageButtonOptions": {
        "format": "png",
        "filename": "BioD_Chart_HighRes",
        "height": 800,
        "width": 1200,
        "scale": 3
    },
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"]
}


SK_COLORS = [
    "#E0002A", "#FF7A00", "#FDB913", "#7A1F3D",
    "#F97316", "#DC2626", "#F59E0B", "#991B1B",
    "#EA580C", "#B91C1C", "#FBBF24", "#374151"
]


def polish_plotly_layout(fig, title=None):
    fig.update_layout(
        template="plotly_white",
        title=title if title else fig.layout.title.text,
        title_font=dict(size=21, family="Arial", color="#111827"),
        font=dict(size=13, family="Arial", color="#374151"),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,1)",
        legend=dict(
            bgcolor="rgba(255,255,255,0.90)",
            bordercolor="rgba(224,0,42,0.16)",
            borderwidth=1,
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="left",
            x=0
        ),
        hoverlabel=dict(
            bgcolor="white",
            bordercolor="#E0002A",
            font_size=13,
            font_family="Arial"
        ),
        margin=dict(t=95, b=72, l=75, r=32)
    )

    fig.update_xaxes(
        showgrid=False,
        linecolor="rgba(17,24,39,0.25)",
        tickfont=dict(size=12, color="#374151")
    )

    fig.update_yaxes(
        gridcolor="rgba(224,0,42,0.10)",
        zerolinecolor="rgba(255,122,0,0.20)",
        linecolor="rgba(17,24,39,0.25)",
        tickfont=dict(size=12, color="#374151")
    )

    return fig


# =====================================================
# 탭
# =====================================================
st.divider()
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Mean Table",
    "📊 Whole BioD Bar Plot",
    "📈 PK Trend Line Plot & AUC",
    "🧪 Candidate Analysis",
    "📄 BioD Report"
])


# -----------------------------------------------------
# Tab 1: Mean Table
# -----------------------------------------------------
with tab1:
    st.markdown('<div class="soft-card">', unsafe_allow_html=True)
    render_section_header(
        "📋 Mean Table",
        "CRO, 물질/그룹, 장기 조건을 선택해 시간점별 평균 %ID/g 값을 표로 확인합니다.",
        label="TABLE"
    )

    table_cros = sorted(master["source_cro"].unique())
    table_organs = sorted(master["organ"].unique())
    table_groups = sorted(master["display_group_id"].unique())

    t_col1, t_col2, t_col3 = st.columns(3)

    with t_col1:
        selected_t_cros = st.multiselect(
            "🏢 CRO",
            options=table_cros,
            default=table_cros
        )

    with t_col2:
        selected_t_groups = st.multiselect(
            "🧪 그룹명/물질",
            options=table_groups,
            default=table_groups
        )

    with t_col3:
        selected_t_organs = st.multiselect(
            "🫀 장기",
            options=table_organs,
            default=table_organs
        )

    table_master = master[
        (master["source_cro"].isin(selected_t_cros)) &
        (master["display_group_id"].isin(selected_t_groups)) &
        (master["organ"].isin(selected_t_organs))
    ]

    if not table_master.empty:
        pivot_df = table_master.pivot_table(
            index=["source_cro", "display_group_id", "organ"],
            columns="timepoint",
            values="percent_id_per_g",
            aggfunc="mean"
        )

        time_order = (
            table_master[["timepoint", "timepoint_hour"]]
            .drop_duplicates()
            .sort_values("timepoint_hour")["timepoint"]
            .tolist()
        )

        ordered_cols = [c for c in time_order if c in pivot_df.columns]
        pivot_df = pivot_df.reindex(columns=ordered_cols).reset_index()

        pivot_df = pivot_df.rename(columns={
            "source_cro": "CRO",
            "display_group_id": "그룹명/물질",
            "organ": "장기(Organ)"
        })

        st.dataframe(pivot_df, use_container_width=True, hide_index=True)

        buffer = io.BytesIO()

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            pivot_df.to_excel(writer, sheet_name="Mean_Table", index=False)

        st.download_button(
            label="📥 현재 표를 Excel로 다운로드",
            data=buffer.getvalue(),
            file_name="BioD_Mean_Table.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        st.warning("⚠️ 선택하신 조건에 일치하는 데이터가 표에 존재하지 않습니다.")

    st.markdown('</div>', unsafe_allow_html=True)


# -----------------------------------------------------
# Tab 2: Bar Plot
# -----------------------------------------------------
with tab2:
    st.markdown('<div class="soft-card">', unsafe_allow_html=True)
    render_section_header(
        "📊 Whole BioD Bar Plot",
        "장기별 %ID/g 평균값을 그룹 단위로 비교합니다. Log scale과 SD error bar를 선택적으로 표시할 수 있습니다.",
        label="VISUAL"
    )

    col_t2_1, col_t2_2 = st.columns([0.5, 0.5])

    with col_t2_1:
        use_log_bar = st.toggle("📉 Y축 로그 스케일", key="log_bar")

    with col_t2_2:
        show_error_bar = st.toggle("📏 SD Error bar 표시", value=True, key="error_bar_toggle")

    chart_data = master.groupby(
        ["display_group_id", "organ", "timepoint", "timepoint_hour"],
        as_index=False
    ).agg(
        mean_id_g=("percent_id_per_g", "mean"),
        std_id_g=("percent_id_per_g", "std")
    )

    available_timepoints = chart_data.sort_values("timepoint_hour")["timepoint"].unique()
    available_organs = chart_data["organ"].unique()

    b_col1, b_col2 = st.columns(2)

    with b_col1:
        selected_b_tps = st.multiselect(
            "⏳ Timepoint",
            options=available_timepoints,
            default=list(available_timepoints)
        )

    with b_col2:
        selected_b_organs = st.multiselect(
            "🫀 Organ",
            options=available_organs,
            default=list(available_organs)
        )

    unique_groups = sorted(chart_data["display_group_id"].unique())
    color_map = {grp: SK_COLORS[i % len(SK_COLORS)] for i, grp in enumerate(unique_groups)}

    if selected_b_tps and selected_b_organs:
        plot_df = chart_data[
            (chart_data["timepoint"].isin(selected_b_tps)) &
            (chart_data["organ"].isin(selected_b_organs))
        ].copy()

        fig_bar = go.Figure()

        added_legends = set()

        trace_order = (
            plot_df[["display_group_id", "timepoint", "timepoint_hour"]]
            .drop_duplicates()
            .sort_values(["display_group_id", "timepoint_hour"])
        )

        for _, row in trace_order.iterrows():
            grp = row["display_group_id"]
            tp_hour = row["timepoint_hour"]

            grp_df = plot_df[
                (plot_df["display_group_id"] == grp) &
                (plot_df["timepoint_hour"] == tp_hour)
            ].sort_values("organ")

            if grp_df.empty:
                continue

            show_leg = grp not in added_legends
            added_legends.add(grp)

            text_labels = grp_df.apply(
                lambda r: f"{r['mean_id_g']:.2f}<br>({r['timepoint']})",
                axis=1
            )

            if show_error_bar:
                error_y_setting = dict(
                    type="data",
                    array=grp_df["std_id_g"].fillna(0),
                    visible=True,
                    thickness=1.6,
                    color="rgba(17,24,39,0.56)"
                )
            else:
                error_y_setting = None

            fig_bar.add_trace(go.Bar(
                x=grp_df["organ"],
                y=grp_df["mean_id_g"],
                name=grp,
                legendgroup=grp,
                error_y=error_y_setting,
                marker=dict(
                    color=color_map[grp],
                    line=dict(color="white", width=1.5)
                ),
                opacity=0.94,
                text=text_labels,
                textposition="outside",
                textfont=dict(size=11, color="#111827"),
                showlegend=show_leg,
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    + "Mean: %{y:.3f} %ID/g<br>"
                    + f"Group: {grp}<br>"
                    + "<extra></extra>"
                )
            ))

        yaxis_title = "%ID/g (Mean ± SD)" if show_error_bar else "%ID/g (Mean)"

        fig_bar.update_layout(
            barmode="group",
            yaxis_title=yaxis_title,
            xaxis_title="Organ",
            xaxis=dict(categoryorder="array", categoryarray=plot_df["organ"].unique()),
            yaxis_type="log" if use_log_bar else "linear"
        )

        fig_bar = polish_plotly_layout(
            fig_bar,
            title="Whole BioD Comparison"
        )

        st.plotly_chart(fig_bar, use_container_width=True, config=plotly_config)

    else:
        st.warning("⚠️ 필터를 선택해 주세요.")

    st.markdown('</div>', unsafe_allow_html=True)


# -----------------------------------------------------
# Tab 3: PK Line Plot & AUC
# -----------------------------------------------------
with tab3:
    st.markdown('<div class="soft-card">', unsafe_allow_html=True)
    render_section_header(
        "📈 PK Trend Line Plot & AUC",
        "선택한 장기에 대해 시간에 따른 %ID/g 변화를 확인하고 AUC_0-last를 계산합니다.",
        label="PK / AUC"
    )

    col_t3_1, col_t3_2 = st.columns([0.5, 0.5])

    with col_t3_1:
        use_log_line = st.toggle("📉 Y축 로그 스케일", key="log_line")

    with col_t3_2:
        show_error_line = st.toggle("📏 SD Error bar 표시", value=True, key="error_line_toggle")

    st.caption("이 탭은 기존 CRO·표시 그룹 기준의 요약입니다. 파일별 분리·공통 구간 AUC 비교는 BioD Report & Candidate Analysis 탭을 사용하세요.")
    legacy_auc_method = st.selectbox("AUC 0시간 처리", ["observed", "hold", "zero"],
        format_func=lambda m: {"observed": "관측 구간만 (AUC_first–last)", "hold": "0시간 = 첫 측정값 (AUC_0–last, 기존 가정)", "zero": "0시간 = 0 (AUC_0–last)"}[m], key="legacy_auc_method")

    selected_line_organs = st.multiselect(
        "🎯 분석할 장기",
        options=available_organs,
        default=[available_organs[0]] if len(available_organs) > 0 else [],
        key="line_organ_filter"
    )

    if selected_line_organs:
        line_cols = st.columns(2)
        auc_results = []

        for i, organ in enumerate(selected_line_organs):
            line_df = chart_data[chart_data["organ"] == organ].copy()
            line_df = line_df.sort_values(["display_group_id", "timepoint_hour"])

            if not line_df.empty:
                if show_error_line:
                    fig_line = px.line(
                        line_df,
                        x="timepoint_hour",
                        y="mean_id_g",
                        error_y="std_id_g",
                        color="display_group_id",
                        markers=True,
                        title=f"Time-Activity Curve: <b>{organ}</b>",
                        labels={
                            "timepoint_hour": "Time after injection (hour)",
                            "mean_id_g": "%ID/g (Mean ± SD)",
                            "display_group_id": "물질명"
                        },
                        color_discrete_map=color_map,
                        template="plotly_white"
                    )
                else:
                    fig_line = px.line(
                        line_df,
                        x="timepoint_hour",
                        y="mean_id_g",
                        color="display_group_id",
                        markers=True,
                        title=f"Time-Activity Curve: <b>{organ}</b>",
                        labels={
                            "timepoint_hour": "Time after injection (hour)",
                            "mean_id_g": "%ID/g (Mean)",
                            "display_group_id": "물질명"
                        },
                        color_discrete_map=color_map,
                        template="plotly_white"
                    )

                # 실제 시간 간격을 반영하기 위해 x축은 timepoint_hour 숫자값 사용
                # 화면 label은 기존 timepoint 문자열(1h, 4h, 24h 등)로 표시
                tick_df = (
                    line_df[["timepoint", "timepoint_hour"]]
                    .drop_duplicates()
                    .sort_values("timepoint_hour")
                )

                fig_line.update_xaxes(
                    type="linear",
                    tickmode="array",
                    tickvals=tick_df["timepoint_hour"].tolist(),
                    ticktext=tick_df["timepoint"].tolist(),
                    title_text="Time after injection"
                )

                fig_line.update_traces(
                    line=dict(width=3.5),
                    marker=dict(size=9.5, line=dict(width=1.6, color="white")),
                    hovertemplate=(
                        "<b>%{x} h</b><br>"
                        + "%ID/g: %{y:.3f}<br>"
                        + "<extra></extra>"
                    )
                )

                fig_line.update_layout(
                    yaxis_type="log" if use_log_line else "linear"
                )

                fig_line = polish_plotly_layout(fig_line)

                # PK 그래프는 제목과 범례가 겹치지 않도록 범례를 그래프 아래쪽으로 이동
                fig_line.update_layout(
                    margin=dict(t=95, b=145, l=75, r=32),
                    legend=dict(
                        orientation="h",
                        yanchor="top",
                        y=-0.28,
                        xanchor="left",
                        x=0,
                        bgcolor="rgba(255,255,255,0.92)",
                        bordercolor="rgba(224,0,42,0.16)",
                        borderwidth=1
                    )
                )



                with line_cols[i % 2]:
                    st.plotly_chart(fig_line, use_container_width=True, config=plotly_config)

                for grp in line_df["display_group_id"].unique():
                    grp_data = line_df[
                        line_df["display_group_id"] == grp
                    ].sort_values("timepoint_hour")

                    if len(grp_data) > 1:
                        times = grp_data["timepoint_hour"].values
                        concs = grp_data["mean_id_g"].values

                        auc_start = float(times[0]) if legacy_auc_method == "observed" else 0.0
                        auc_val, auc_status = integrate_curve(times, concs, legacy_auc_method, auc_start, float(times[-1]))

                        auc_results.append({
                            "장기(Organ)": organ,
                            "물질명": grp,
                            "AUC": round(auc_val, 2),
                            "시작(h)": auc_start,
                            "종료(h)": float(times[-1]),
                            "0시간 처리": legacy_auc_method,
                            "상태": auc_status
                        })

        if auc_results:
            st.markdown("##### 📐 AUC Summary (%ID/g·h)")
            auc_df = pd.DataFrame(auc_results)
            st.dataframe(auc_df, use_container_width=True, hide_index=True)

            auc_pivot = auc_df.pivot_table(
                index="장기(Organ)",
                columns="물질명",
                values="AUC",
                aggfunc="first"
            ).fillna("-")

            st.dataframe(auc_pivot, use_container_width=True)

    else:
        st.info("장기를 하나 이상 선택해 주세요.")

    st.markdown('</div>', unsafe_allow_html=True)

with tab4:
    render_analysis(analysis_input, tab5)
