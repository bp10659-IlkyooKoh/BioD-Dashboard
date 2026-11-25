"""Read Molim long-form BioD tables without conflating compound and cohort."""
import re

import pandas as pd


ALIASES = {
    "compound": ["compound", "compound name", "compound id", "test article", "test article name",
                 "material", "material name", "substance", "drug", "물질명", "시험물질", "시험물질명", "약물명"],
    "group": ["group", "group name", "treatment group", "dose group", "군", "그룹", "군명"],
    "time": ["timepoint", "time point (h)", "time point (hr)", "timepoint (hour)",
             "time", "time (h)", "time (hr)", "시간", "시간 (h)"],
    "animal": ["mouse", "mouse id", "mouse no", "animal id", "animal no", "animal", "개체번호", "개체 ID"],
    "organ": ["organ", "organ name", "tissue", "tissue name", "장기", "조직"],
    "value": ["%id/g", "id/g", "uptake (%id/g)", "%id/g (mean)"],
}


def _key(value):
    return re.sub(r"[^\w%]|_", "", str(value).strip().lower())


def _column(columns, role):
    normalized = {_key(c): c for c in columns}
    for alias in ALIASES[role]:
        if _key(alias) in normalized:
            return normalized[_key(alias)]
    # Preserve legacy descriptive headers such as 'Measured uptake (%ID/g)'.
    # Identity columns use exact aliases to avoid mistaking Animal Group for Group.
    if role in {"value", "time", "organ", "animal"}:
        for alias in ALIASES[role]:
            for key, column in normalized.items():
                if _key(alias) in key:
                    return column
    return None


def parse_mollim_workbook(file, extract_hour):
    """Prefer explicit compound identity; preserve group context where provided."""
    file.seek(0)
    xls = pd.ExcelFile(file)
    results, diagnostics = [], []
    for sheet in xls.sheet_names:
        file.seek(0)
        raw = pd.read_excel(file, sheet_name=sheet, header=None)
        header = None
        columns = None
        for i in range(min(30, len(raw))):
            candidate = raw.iloc[i].tolist()
            found = {role: _column(candidate, role) for role in ALIASES}
            if all(found[r] is not None for r in ["time", "organ", "value"]):
                header, columns = i, found
                break
        if header is None:
            diagnostics.append({"sheet": sheet, "status": "시간·장기·%ID/g 헤더를 찾지 못함"})
            continue
        table = raw.iloc[header + 1:].copy()
        table.columns = raw.iloc[header].tolist()
        # Ambiguous duplicated headers must not be silently selected.
        used = [c for c in columns.values() if c is not None]
        if any(list(table.columns).count(c) != 1 for c in used):
            diagnostics.append({"sheet": sheet, "status": "인식 대상 헤더가 중복됨"})
            continue
        identity = columns["compound"] if columns["compound"] is not None else columns["group"]
        if identity is None:
            # Legacy one-compound-per-sheet layout.
            group = pd.Series(sheet, index=table.index)
        else:
            group = table[identity].replace(r"^\s*$", pd.NA, regex=True).ffill()
        organ = table[columns["organ"]].astype("string").str.strip()
        value = pd.to_numeric(table[columns["value"]], errors="coerce")
        time = table[columns["time"]].replace(r"^\s*$", pd.NA, regex=True).ffill()
        temp = pd.DataFrame({"group_id": group, "timepoint": time,
                             "animal_id": table[columns["animal"]] if columns["animal"] is not None else "",
                             "organ": organ.str.upper(), "percent_id_per_g": value,
                             "source_sheet": sheet, "compound_column": str(identity) if identity is not None else "(시트명)"})
        # Keep the original cohort visible without interpreting it as a compound.
        if columns["group"] is not None:
            temp["original_cohort"] = table[columns["group"]]
        temp["timepoint_hour"] = temp.timepoint.apply(extract_hour)
        valid = temp.group_id.notna() & organ.notna() & organ.ne("") & value.notna()
        temp = temp.loc[valid].copy()
        temp["group_id"] = temp.group_id.astype(str).str.strip()
        if not temp.empty:
            results.append(temp)
        diagnostics.append({"sheet": sheet, "status": "ok", "compound_column": str(identity) if identity is not None else "(시트명)",
                            "groups": int(temp.group_id.nunique()), "rows": len(temp)})
    out = pd.concat(results, ignore_index=True) if results else pd.DataFrame()
    out.attrs["parse_diagnostics"] = diagnostics
    return out
