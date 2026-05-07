import csv
import re
import base64
from datetime import date, datetime
from io import StringIO

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st


# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Tanishq Precampaign Segmentation Tool For Store Campiagns",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp {
        background: linear-gradient(180deg, #081120 0%, #0b1728 45%, #0f1f35 100%);
        color: #eaf2ff;
    }

    .block-container {
        padding-top: 1.9rem !important;
        padding-bottom: 1rem !important;
    }

    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #ffffff;
        margin-top: 12px;
        margin-bottom: 0.2rem;
        padding-top: 0;
        line-height: 1.3;
    }

    .sub-title {
        font-size: 1rem;
        color: #b8c7e0;
        margin-top: 0;
        margin-bottom: 0.9rem;
    }

    .metric-card {
        background: linear-gradient(135deg, rgba(30,41,59,0.95), rgba(15,23,42,0.95));
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 18px;
        padding: 16px 18px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.25);
        text-align: center;
    }

    .count-card {
        background: linear-gradient(135deg, #0f172a, #111827);
        border: 1px solid rgba(59, 130, 246, 0.35);
        border-radius: 20px;
        padding: 22px;
        margin-top: 8px;
        margin-bottom: 18px;
        box-shadow: 0 10px 28px rgba(0,0,0,0.28);
    }

    .count-card-title {
        color: #c7d8ff;
        font-size: 1rem;
        margin-bottom: 16px;
        text-align: center;
        font-weight: 700;
    }

    .count-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
    }

    .count-box {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(148,163,184,0.15);
        border-radius: 16px;
        padding: 18px;
        text-align: center;
        margin-top: -8px;
    }

    .count-label {
        color: #c7d8ff;
        font-size: 0.95rem;
        margin-bottom: 8px;
    }

    .count-value {
        color: #ffffff;
        font-size: 2rem;
        font-weight: 800;
    }

    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0b1220 0%, #111b2e 100%);
        border-right: 1px solid rgba(148, 163, 184, 0.15);
    }

    div[data-testid="stSidebar"] * {
        color: #eef4ff;
    }

    .stButton > button, .stDownloadButton > button {
        border-radius: 12px;
        font-weight: 700;
        height: 3rem;
        border: 0;
    }

    .stButton > button {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        color: white;
    }

    .stDownloadButton > button {
        background: linear-gradient(135deg, #059669, #047857);
        color: white;
    }

    .stTextInput > div > div > input,
    .stTextArea textarea,
    .stDateInput input,
    .stSelectbox div[data-baseweb="select"] > div,
    .stMultiSelect div[data-baseweb="select"] > div,
    .stRadio div[role="radiogroup"] {
        border-radius: 12px !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 Tanishq Precampaign Segmentation Tool For Store Campiagns</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Create campaign base, view running step counts, and download final cedilla CSV.</div>',
    unsafe_allow_html=True
)


# ============================================================
# INTERNAL CONFIG
# ============================================================
ENCODED_DB_PASSWORD = "UmVkc2hpZnQjMTMx"


def decode_db_password(encoded_text: str) -> str:
    return base64.b64decode(encoded_text.encode("utf-8")).decode("utf-8")


DEFAULTS = {
    "db_host": "tcl-it-edw-redshift-prod-03.cktijfqqwie2.ap-south-1.redshift.amazonaws.com",
    "db_port": 5439,
    "db_name": "rsdev01",
    "db_user": "e0946238_priyankar",
    "db_pass": "Redshift#131",

    "mode": "WHATSAPP",
    "base_type": "ENCIRCLE + CROSS CHANNEL",
    "cam_id": "CAM-16385",
    "campaign_name": "Tanishq TBM bangle mela",
    "brand_code": "TSQ",
    "final_cut": "CUT1",

    "txn_start_date": "2021-04-01",
    "st_dt": "2026-03-11",
    "ed_dt": "2026-03-19",

    "delimiter": "ç",
    "export_encoding": "utf-8-sig",
    "preview_limit": 20,

    "enable_high_value_filter": False,
    "high_value_min_bill": 300000
}


# ============================================================
# SESSION STATE
# ============================================================
def init_state():
    defaults = {
        "cam_id": "",
        "campaign_name": "",
        "mode": "",
        "base_type": "",
        "txn_start_date": date.fromisoformat(DEFAULTS["txn_start_date"]),

        # Common filters for combined mode
        "common_filter_fields": [],
        "city_text": "",
        "region_text": "",
        "state_text": "",
        "common_store_code_text": "",
        "common_pincode_text": "",

        # Encircle standalone / combined
        "encircle_filter_fields": [],
        "encircle_city_text": "",
        "encircle_region_text": "",
        "encircle_state_text": "",
        "encircle_store_code_text": "",
        "encircle_pincode_text": "",

        # Cross standalone / combined
        "cross_filter_fields": [],
        "cross_city_text": "",
        "cross_region_text": "",
        "cross_state_text": "",
        "cross_store_code_text": "",
        "cross_pincode_text": "",

        "enable_high_value_filter": DEFAULTS["enable_high_value_filter"],
        "high_value_min_bill": DEFAULTS["high_value_min_bill"],

        "last_counts": {},
        "step_count_rows": [],
        "download_csv_bytes": None,
        "download_csv_name": None,
        "flow_completed": False,
        "active_run_tables": {},
        "preview_df": None
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def clear_form():
    keys_to_reset = {
        "cam_id": "",
        "campaign_name": "",
        "mode": "",
        "base_type": "",
        "txn_start_date": date.fromisoformat(DEFAULTS["txn_start_date"]),

        "common_filter_fields": [],
        "city_text": "",
        "region_text": "",
        "state_text": "",
        "common_store_code_text": "",
        "common_pincode_text": "",

        "encircle_filter_fields": [],
        "encircle_city_text": "",
        "encircle_region_text": "",
        "encircle_state_text": "",
        "encircle_store_code_text": "",
        "encircle_pincode_text": "",

        "cross_filter_fields": [],
        "cross_city_text": "",
        "cross_region_text": "",
        "cross_state_text": "",
        "cross_store_code_text": "",
        "cross_pincode_text": "",

        "enable_high_value_filter": DEFAULTS["enable_high_value_filter"],
        "high_value_min_bill": DEFAULTS["high_value_min_bill"],

        "last_counts": {},
        "step_count_rows": [],
        "download_csv_bytes": None,
        "download_csv_name": None,
        "flow_completed": False,
        "active_run_tables": {},
        "preview_df": None
    }

    for k, v in keys_to_reset.items():
        st.session_state[k] = v


init_state()


# ============================================================
# HELPERS
# ============================================================
def sql_quote(value: str) -> str:
    return str(value).replace("'", "''")


def sql_list(values):
    escaped = [f"'{sql_quote(str(v).strip())}'" for v in values if str(v).strip()]
    return "(" + ",".join(escaped) + ")" if escaped else "('')"


def parse_pasted_filter_values(text: str):
    if text is None:
        return []
    raw = str(text).strip()
    if not raw:
        return []

    raw = raw.replace("\n", ",").replace("\r", ",").replace("\t", ",").replace(";", ",")
    parts = [p.strip() for p in raw.split(",") if p.strip()]

    cleaned = []
    for p in parts:
        p = p.strip().strip("'").strip('"').strip()
        if p:
            cleaned.append(p)

    out = []
    seen = set()
    for x in cleaned:
        key = x.upper()
        if key not in seen:
            seen.add(key)
            out.append(x)
    return out


def optional_in_filter(column_expr: str, values):
    if not values:
        return ""
    return f" AND {column_expr} IN {sql_list(values)} "


def get_conn(cfg):
    return psycopg2.connect(
        host=cfg["db_host"],
        port=int(cfg["db_port"]),
        dbname=cfg["db_name"],
        user=cfg["db_user"],
        password=cfg["db_pass"]
    )


def fetch_one(cur, query: str):
    cur.execute(query)
    return cur.fetchone()


def fetch_scalar(cur, query: str):
    cur.execute(query)
    row = cur.fetchone()
    if row is None:
        return None
    if isinstance(row, dict):
        return list(row.values())[0]
    return row[0]


def execute_sql(cur, sql_text: str):
    cur.execute(sql_text)


def output_file_name(cam_id: str, mode: str):
    mode_short = {
        "WHATSAPP": "WA",
        "SMS": "SMS",
        "RCS": "RCS"
    }[mode.upper().strip()]
    cam_value = cam_id.strip().replace("CAM-", "").replace("cam-", "")
    return f"EDW_SFMC_TANISHQ_{mode_short}_{cam_value}.csv"


def resultset_to_cedilla_csv_bytes(cur, query: str, delimiter="ç", encoding="utf-8-sig", batch_size=50000):
    cur.execute(query)
    output = StringIO()
    writer = csv.writer(output, delimiter=delimiter, lineterminator="\n")

    headers = [desc[0] for desc in cur.description]
    writer.writerow(headers)

    while True:
        rows = cur.fetchmany(batch_size)
        if not rows:
            break
        for row in rows:
            if isinstance(row, dict):
                writer.writerow([row.get(col) for col in headers])
            else:
                writer.writerow(list(row))

    return output.getvalue().encode(encoding)


def make_safe_suffix(cam_id: str) -> str:
    cleaned = re.sub(r'[^A-Za-z0-9]+', '_', str(cam_id).strip())
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{cleaned}_{ts}"


def count_row_to_dict(row):
    if row is None:
        return {"distinct_ids": None, "rows": None}
    if isinstance(row, dict):
        return {"distinct_ids": row.get("distinct_ids"), "rows": row.get("rows")}
    return {"distinct_ids": row[0], "rows": row[1]}


def fmt_num(val):
    if val is None or val == "":
        return None
    try:
        return f"{int(val):,}"
    except Exception:
        return val


def append_step_count(stage_name, distinct_ids=None, rows=None):
    st.session_state.step_count_rows.append({
        "Stage": stage_name,
        "Distinct IDs": fmt_num(distinct_ids),
        "Total No of Rows": fmt_num(rows)
    })


def render_running_step_counts():
    return


def render_final_count_card(final_distinct_ids, final_rows):
    st.markdown(
        f"""
        <div class="count-card">
            <div class="count-card-title">Final Extract Count Summary</div>
            <div class="count-grid">
                <div class="count-box">
                    <div class="count-label">Distinct ID Count</div>
                    <div class="count-value">{fmt_num(0 if final_distinct_ids is None else final_distinct_ids)}</div>
                </div>
                <div class="count-box">
                    <div class="count-label">Total No of Rows</div>
                    <div class="count-value">{fmt_num(0 if final_rows is None else final_rows)}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# MODE EXCLUSIONS
# ============================================================
def get_mode_exclusion_sql_for_tsq(mode: str):
    mode = mode.upper().strip()

    if mode == "WHATSAPP":
        return """
        AND C.REGISTERED_MOBILENUMBER NOT IN (
            SELECT DISTINCT MOBILE
            FROM CAMPAIGN_ALL_MEDIUM_BLACKLISTED
            WHERE MOBILE IS NOT NULL
        )
        AND C.REGISTERED_MOBILENUMBER NOT IN (
            SELECT MOBILE
            FROM whatsapp_unsubscribe_list
            WHERE BRAND = 'TANISHQ'
        )
        AND C.REGISTERED_MOBILENUMBER NOT IN (
            SELECT MOBILE
            FROM WHATSAPP_BLACKLISTED_01_03
        )
        AND C.registered_mobilenumber NOT IN (
            SELECT DISTINCT mobile_number
            FROM CARTESIAN_CON.EDW_PERMANANT_FAILURE_NUMBER
            WHERE permanant_failure_tag = 'Y'
        )
        """
    elif mode == "SMS":
        return """
        AND C.REGISTERED_MOBILENUMBER NOT IN (
            SELECT DISTINCT MOBILE
            FROM CAMPAIGN_ALL_MEDIUM_BLACKLISTED
            WHERE MOBILE IS NOT NULL
        )
        AND C.registered_mobilenumber NOT IN (
            SELECT DISTINCT mobile_number
            FROM CARTESIAN_CON.EDW_PERMANANT_FAILURE_NUMBER
            WHERE permanant_failure_tag = 'Y'
        )
        AND A.MOB_MTCHED_LYLTY_ID IN (
            SELECT ulpmembershipid
            FROM CARTESIAN_CON.EDW_NONDND_CARDS
            WHERE ulpmembershipid IS NOT NULL
        )
        """
    elif mode == "RCS":
        return """
        AND C.registered_mobilenumber IN (
            SELECT SUBSTRING(mobile_no, 3)
            FROM cartesian_con.edw_rcs_non_rcs_data
            WHERE flag = 'RCS'
        )
        AND C.REGISTERED_MOBILENUMBER NOT IN (
            SELECT DISTINCT MOBILE
            FROM CAMPAIGN_ALL_MEDIUM_BLACKLISTED
            WHERE MOBILE IS NOT NULL
        )
        AND C.registered_mobilenumber NOT IN (
            SELECT DISTINCT mobile_number
            FROM CARTESIAN_CON.EDW_PERMANANT_FAILURE_NUMBER
            WHERE permanant_failure_tag = 'Y'
        )
        AND C.registered_mobilenumber NOT IN (
            SELECT mobile
            FROM RCS_Unsubcribe_List
            WHERE brand = 'MIA'
              AND OPT_OUT_FLAG = 'Y'
        )
        """
    else:
        raise ValueError("Invalid mode. Use WHATSAPP / SMS / RCS")


def get_mode_exclusion_sql_for_cross(mode: str):
    mode = mode.upper().strip()

    if mode == "WHATSAPP":
        return """
        AND C.REGISTERED_MOBILENUMBER NOT IN (
            SELECT DISTINCT MOBILE
            FROM CAMPAIGN_ALL_MEDIUM_BLACKLISTED
            WHERE MOBILE IS NOT NULL
        )
        AND C.REGISTERED_MOBILENUMBER NOT IN (
            SELECT MOBILE
            FROM whatsapp_unsubscribe_list
        )
        AND C.REGISTERED_MOBILENUMBER NOT IN (
            SELECT MOBILE
            FROM WHATSAPP_BLACKLISTED_01_03
        )
        AND C.registered_mobilenumber NOT IN (
            SELECT DISTINCT mobile_number
            FROM CARTESIAN_CON.EDW_PERMANANT_FAILURE_NUMBER
            WHERE permanant_failure_tag = 'Y'
        )
        """
    elif mode == "SMS":
        return """
        AND C.REGISTERED_MOBILENUMBER NOT IN (
            SELECT DISTINCT MOBILE
            FROM CAMPAIGN_ALL_MEDIUM_BLACKLISTED
            WHERE MOBILE IS NOT NULL
        )
        AND C.registered_mobilenumber NOT IN (
            SELECT DISTINCT mobile_number
            FROM CARTESIAN_CON.EDW_PERMANANT_FAILURE_NUMBER
            WHERE permanant_failure_tag = 'Y'
        )
        AND A.MOB_MTCHED_LYLTY_ID IN (
            SELECT ulpmembershipid
            FROM CARTESIAN_CON.EDW_NONDND_CARDS
            WHERE ulpmembershipid IS NOT NULL
        )
        """
    elif mode == "RCS":
        return """
        AND C.registered_mobilenumber IN (
            SELECT SUBSTRING(mobile_no, 3)
            FROM cartesian_con.edw_rcs_non_rcs_data
            WHERE flag = 'RCS'
        )
        AND C.REGISTERED_MOBILENUMBER NOT IN (
            SELECT DISTINCT MOBILE
            FROM CAMPAIGN_ALL_MEDIUM_BLACKLISTED
            WHERE MOBILE IS NOT NULL
        )
        AND C.registered_mobilenumber NOT IN (
            SELECT DISTINCT mobile_number
            FROM CARTESIAN_CON.EDW_PERMANANT_FAILURE_NUMBER
            WHERE permanant_failure_tag = 'Y'
        )
        AND C.registered_mobilenumber NOT IN (
            SELECT mobile
            FROM RCS_Unsubcribe_List
            WHERE brand = 'MIA'
              AND OPT_OUT_FLAG = 'Y'
        )
        """
    else:
        raise ValueError("Invalid mode. Use WHATSAPP / SMS / RCS")


# ============================================================
# FILTER BUILDERS
# ============================================================
def build_encircle_optional_filter_sql(cfg):
    sql_parts = []
    sql_parts.append(optional_in_filter("A.store_code", cfg["tsq_store_codes_list"]))
    sql_parts.append(optional_in_filter("CAST(C.pincode AS VARCHAR)", cfg["encircle_pincodes_list"]))
    sql_parts.append(optional_in_filter("UPPER(A.city)", [x.upper() for x in cfg["encircle_city_list"]]))
    sql_parts.append(optional_in_filter("UPPER(A.region)", [x.upper() for x in cfg["encircle_region_list"]]))
    sql_parts.append(optional_in_filter("UPPER(A.state)", [x.upper() for x in cfg["encircle_state_list"]]))
    return "\n".join([x for x in sql_parts if x.strip()])


def build_cross_optional_filter_sql_inside(cfg):
    conditions = []

    if cfg["cross_pincodes_list"]:
        conditions.append(f"CAST(C.pincode AS VARCHAR) IN {sql_list(cfg['cross_pincodes_list'])}")
    if cfg["cross_store_codes_list"]:
        conditions.append(f"SM.store_code IN {sql_list(cfg['cross_store_codes_list'])}")
    if cfg["cross_city_list"]:
        conditions.append(f"UPPER(SM.city) IN {sql_list([x.upper() for x in cfg['cross_city_list']])}")
    if cfg["cross_region_list"]:
        conditions.append(f"UPPER(SM.region) IN {sql_list([x.upper() for x in cfg['cross_region_list']])}")
    if cfg["cross_state_list"]:
        conditions.append(f"UPPER(SM.state) IN {sql_list([x.upper() for x in cfg['cross_state_list']])}")

    if not conditions:
        return ""

    return " AND (" + " OR ".join(conditions) + ") "


# ============================================================
# FILTER MAPPING
# ============================================================
def get_filter_lists_from_ui():
    base_type = st.session_state.base_type

    common_city = parse_pasted_filter_values(st.session_state.city_text)
    common_region = parse_pasted_filter_values(st.session_state.region_text)
    common_state = parse_pasted_filter_values(st.session_state.state_text)
    common_store = parse_pasted_filter_values(st.session_state.common_store_code_text)
    common_pin = parse_pasted_filter_values(st.session_state.common_pincode_text)

    enc_city = parse_pasted_filter_values(st.session_state.encircle_city_text)
    enc_region = parse_pasted_filter_values(st.session_state.encircle_region_text)
    enc_state = parse_pasted_filter_values(st.session_state.encircle_state_text)
    enc_store = parse_pasted_filter_values(st.session_state.encircle_store_code_text)
    enc_pin = parse_pasted_filter_values(st.session_state.encircle_pincode_text)

    cross_city = parse_pasted_filter_values(st.session_state.cross_city_text)
    cross_region = parse_pasted_filter_values(st.session_state.cross_region_text)
    cross_state = parse_pasted_filter_values(st.session_state.cross_state_text)
    cross_store = parse_pasted_filter_values(st.session_state.cross_store_code_text)
    cross_pin = parse_pasted_filter_values(st.session_state.cross_pincode_text)

    if base_type == "ENCIRCLE":
        return {
            "tsq_store_codes_list": enc_store,
            "encircle_pincodes_list": enc_pin,
            "encircle_city_list": enc_city,
            "encircle_region_list": enc_region,
            "encircle_state_list": enc_state,

            "cross_store_codes_list": [],
            "cross_pincodes_list": [],
            "cross_city_list": [],
            "cross_region_list": [],
            "cross_state_list": []
        }

    if base_type == "CROSS CHANNEL":
        return {
            "tsq_store_codes_list": [],
            "encircle_pincodes_list": [],
            "encircle_city_list": [],
            "encircle_region_list": [],
            "encircle_state_list": [],

            "cross_store_codes_list": cross_store,
            "cross_pincodes_list": cross_pin,
            "cross_city_list": cross_city,
            "cross_region_list": cross_region,
            "cross_state_list": cross_state
        }

    return {
        "tsq_store_codes_list": list(dict.fromkeys(enc_store + common_store)),
        "encircle_pincodes_list": list(dict.fromkeys(enc_pin + common_pin)),
        "encircle_city_list": list(dict.fromkeys(enc_city + common_city)),
        "encircle_region_list": list(dict.fromkeys(enc_region + common_region)),
        "encircle_state_list": list(dict.fromkeys(enc_state + common_state)),

        "cross_store_codes_list": list(dict.fromkeys(cross_store + common_store)),
        "cross_pincodes_list": list(dict.fromkeys(cross_pin + common_pin)),
        "cross_city_list": list(dict.fromkeys(cross_city + common_city)),
        "cross_region_list": list(dict.fromkeys(cross_region + common_region)),
        "cross_state_list": list(dict.fromkeys(cross_state + common_state))
    }


# ============================================================
# SQL BUILDERS
# ============================================================
def build_tsq_sql(cfg):
    exclusion_sql = get_mode_exclusion_sql_for_tsq(cfg["mode"])
    encircle_optional_sql = build_encircle_optional_filter_sql(cfg)

    high_value_select = ", sum(T.ucp_value_gross) as BILL_VALUE"
    high_value_where = ""
    if cfg.get("enable_high_value_filter"):
        high_value_where = f" AND BILL_VALUE > {int(cfg['high_value_min_bill'])} "

    return f"""
    DROP TABLE IF EXISTS {cfg['tsq_table']};

    CREATE TABLE {cfg['tsq_table']} AS
    SELECT DISTINCT
        A.MOB_MTCHED_LYLTY_ID,
        A.STATE,
        A.REGION,
        A.CITY,
        A.store_code,
        A.channel
    FROM (
        SELECT DISTINCT
            M.MOB_MTCHED_LYLTY_ID,
            SM.region,
            SM.STATE,
            T.BILL_DATE,
            SM.store_code,
            SM.city,
            T.channel
            {high_value_select},
            ROW_NUMBER() OVER (
                PARTITION BY M.mob_mtched_lylty_id
                ORDER BY T.BILL_DATE DESC
            ) AS RNK
        FROM SEM_IMC.V_FCT_RTL_C360_TRANSACTION_BI T
        INNER JOIN SEM_PU_CUST_ALL.V_TGT_CUST_ALL_UCIC_LYLTY_MAPNG_BI M
            ON T.UCIC = M.UCIC
        INNER JOIN analytics_datamart.store_master_final SM
            ON T.STORECODE = SM.OLD_STORE_CODE
        INNER JOIN SEM_PU_CUST_ALL.V_DIM_PSX_GLD_EDW_ALL_BI C
            ON M.MOB_MTCHED_LYLTY_ID = C.ULPMEMBERSHIPID
        WHERE STORE_TAG IN ('GOLDPLUS','TANISHQ')
          AND M.MOB_MTCHED_LYLTY_ID IS NOT NULL
          AND M.MOB_MTCHED_LYLTY_ID <> '0'
          AND M.MOB_MTCHED_LYLTY_ID <> ''
          AND T.BILL_DATE >= '{sql_quote(cfg["txn_start_date"])}'
        GROUP BY
            M.MOB_MTCHED_LYLTY_ID,
            SM.region,
            SM.STATE,
            T.BILL_DATE,
            SM.store_code,
            SM.city,
            T.channel
    ) A
    INNER JOIN SEM_PU_CUST_ALL.V_DIM_PSX_GLD_EDW_ALL_BI C
        ON A.MOB_MTCHED_LYLTY_ID = C.ULPMEMBERSHIPID
    INNER JOIN CARTESIAN_CON.EDW_CAMPAIGNS_VIEW GCT
        ON GCT.ULPMEMBERSHIPID = C.ULPMEMBERSHIPID
    WHERE A.MOB_MTCHED_LYLTY_ID IS NOT NULL
      AND C.MOBILE_FLAG = 'V'
      AND RNK = 1
      {encircle_optional_sql}
      {high_value_where}
      {exclusion_sql}
    ;
    """


def build_cross_sql(cfg):
    exclusion_sql = get_mode_exclusion_sql_for_cross(cfg["mode"])
    cross_optional_sql = build_cross_optional_filter_sql_inside(cfg)

    return f"""
    DROP TABLE IF EXISTS {cfg['cross_table']};

    CREATE TABLE {cfg['cross_table']} AS
    SELECT DISTINCT
        A.MOB_MTCHED_LYLTY_ID,
        A.STATE,
        A.REGION,
        A.CITY,
        A.store_code,
        A.channel
    FROM (
        SELECT DISTINCT
            M.MOB_MTCHED_LYLTY_ID,
            SM.region,
            SM.STATE,
            T.BILL_DATE,
            SM.store_code,
            SM.city,
            T.channel,
            ROW_NUMBER() OVER (
                PARTITION BY M.mob_mtched_lylty_id
                ORDER BY T.BILL_DATE DESC
            ) AS RNK
        FROM SEM_IMC.V_FCT_RTL_C360_TRANSACTION_BI T
        INNER JOIN SEM_PU_CUST_ALL.V_TGT_CUST_ALL_UCIC_LYLTY_MAPNG_BI M
            ON T.UCIC = M.UCIC
        INNER JOIN analytics_datamart.store_master_final SM
            ON T.STORECODE = SM.OLD_STORE_CODE
        INNER JOIN SEM_PU_CUST_ALL.V_DIM_PSX_GLD_EDW_ALL_BI C
            ON M.MOB_MTCHED_LYLTY_ID = C.ULPMEMBERSHIPID
        WHERE STORE_TAG NOT IN ('GOLDPLUS','TANISHQ')
          AND T.CHANNEL <> 'TANISHQ'
          AND M.MOB_MTCHED_LYLTY_ID IS NOT NULL
          AND M.MOB_MTCHED_LYLTY_ID <> '0'
          AND M.MOB_MTCHED_LYLTY_ID <> ''
          {cross_optional_sql}
    ) A
    INNER JOIN SEM_PU_CUST_ALL.V_DIM_PSX_GLD_EDW_ALL_BI C
        ON A.MOB_MTCHED_LYLTY_ID = C.ULPMEMBERSHIPID
    INNER JOIN CARTESIAN_CON.EDW_CAMPAIGNS_VIEW GCT
        ON GCT.ULPMEMBERSHIPID = C.ULPMEMBERSHIPID
    WHERE C.MOBILE_FLAG = 'V'
      AND RNK = 1
      AND A.MOB_MTCHED_LYLTY_ID IS NOT NULL
      {exclusion_sql}
      AND A.MOB_MTCHED_LYLTY_ID NOT IN (
          SELECT DISTINCT MOB_MTCHED_LYLTY_ID
          FROM {cfg['tsq_table']}
      )
    ;
    """


def build_cross_filtered_sql(cfg):
    return f"""
    DROP TABLE IF EXISTS {cfg['cross_filtered_table']};

    CREATE TABLE {cfg['cross_filtered_table']} AS
    SELECT A.*
    FROM {cfg['cross_table']} A
    LEFT JOIN (
        SELECT mob_mtched_lylty_id
        FROM SEM_IMC.V_FCT_RTL_C360_TRANSACTION_BI I
        GROUP BY 1
    ) B
      ON A.mob_mtched_lylty_id = B.mob_mtched_lylty_id
    WHERE B.mob_mtched_lylty_id IS NULL
    ;
    """


def build_overall_sql(cfg):
    if cfg["base_type"] == "ENCIRCLE":
        union_sql = f"""
            SELECT DISTINCT mob_mtched_lylty_id, REGION, STATE, CITY, STORE_CODE, channel
            FROM {cfg['tsq_table']}
        """
    elif cfg["base_type"] == "CROSS CHANNEL":
        union_sql = f"""
            SELECT DISTINCT mob_mtched_lylty_id, REGION, STATE, CITY, STORE_CODE, channel
            FROM {cfg['cross_filtered_table']}
        """
    else:
        union_sql = f"""
            SELECT DISTINCT mob_mtched_lylty_id, REGION, STATE, CITY, STORE_CODE, channel
            FROM {cfg['tsq_table']}
            UNION
            SELECT DISTINCT mob_mtched_lylty_id, REGION, STATE, CITY, STORE_CODE, channel
            FROM {cfg['cross_filtered_table']}
        """

    return f"""
    DROP TABLE IF EXISTS {cfg['overall_table']};

    CREATE TABLE {cfg['overall_table']} AS
    SELECT DISTINCT A.*
    FROM (
        {union_sql}
    ) A
    INNER JOIN SEM_PU_CUST_ALL.V_TGT_CUST_ALL_UCIC_LYLTY_MAPNG_BI M
        ON A.mob_mtched_lylty_id = M.mob_mtched_lylty_id
    INNER JOIN SEM_PU_CUST_ALL.V_DIM_PSX_GLD_EDW_ALL_BI C
        ON M.MOB_MTCHED_LYLTY_ID = C.ULPMEMBERSHIPID
    ;
    """


def build_campaign_load_sql(cfg):
    return f"""
    DELETE FROM cartesian_con.CAMP_ACTIVE_EDW2
    WHERE CRCDR = '{sql_quote(cfg["cam_id"])}';

    INSERT INTO cartesian_con.CAMP_ACTIVE_EDW2 (
        IS_PROCESSED,
        CARDNO,
        CRCDR,
        TARGET_CONTROL_TAG,
        MOBILE,
        EMAIL,
        VALID_MOBILE_TAG_F,
        VALID_EMAIL_TAG_F,
        st_dt,
        ed_dt,
        ENROLL_STORE,
        ENROLL_CITY,
        ENROLL_STATE,
        ENROLL_REGION,
        ENROLL_CHANNEL,
        FIRSTNAME,
        LASTNAME,
        CUST_AGE,
        GENDER,
        DOB,
        DOA,
        FINAL_CUTS
    )
    SELECT DISTINCT
        -1,
        A.ULPMEMBERSHIPID,
        '{sql_quote(cfg["cam_id"])}',
        A.EDW_GLOBAL_CONTROL_TAG,
        A.REGISTERED_MOBILENUMBER,
        A.REGISTERED_EMAIL,
        A.MOBILE_FLAG,
        A.EMAIL_VALID_FLAG,
        '{sql_quote(cfg["st_dt"])}'::date,
        '{sql_quote(cfg["ed_dt"])}'::date,
        A.ENROLLMENTSTORECODE,
        A.CITY,
        A.STATE,
        A.REGION,
        A.ENROLLMENTCHANNELCODE,
        A.FIRSTNAME,
        A.LASTNAME,
        A."AGE",
        A.GENDER,
        A.DOB,
        A.ANNIVERSARY,
        '{sql_quote(cfg["final_cut"])}'
    FROM (
        SELECT DISTINCT
            C.ULPMEMBERSHIPID,
            GCT.EDW_GLOBAL_CONTROL_TAG,
            C.REGISTERED_MOBILENUMBER,
            C.REGISTERED_EMAIL,
            C.MOBILE_FLAG,
            C.EMAIL_VALID_FLAG,
            J.STORE_CODE AS ENROLLMENTSTORECODE,
            J.CITY,
            J.STATE,
            J.REGION,
            J.CHANNEL AS ENROLLMENTCHANNELCODE,
            C.FIRSTNAME,
            C.LASTNAME,
            C."AGE",
            C.GENDER,
            C.DOB,
            C.ANNIVERSARY,
            ROW_NUMBER() OVER (
                PARTITION BY C.ULPMEMBERSHIPID
                ORDER BY C.enrollmentdate DESC
            ) AS RNK
        FROM SEM_IMC.V_FCT_RTL_C360_TRANSACTION_BI I
        INNER JOIN SEM_PU_CUST_ALL.V_TGT_CUST_ALL_UCIC_LYLTY_MAPNG_BI M
            ON I.UCIC = M.UCIC
        INNER JOIN SEM_PU_CUST_ALL.V_DIM_PSX_GLD_EDW_ALL_BI C
            ON M.MOB_MTCHED_LYLTY_ID = C.ULPMEMBERSHIPID
        INNER JOIN CARTESIAN_CON.STORE_MASTER_FINAL S
            ON I.STORECODE = S.OLD_STORE_CODE
        INNER JOIN CARTESIAN_CON.EDW_CAMPAIGNS_VIEW GCT
            ON GCT.ULPMEMBERSHIPID = C.ULPMEMBERSHIPID
        INNER JOIN {cfg['overall_table']} J
            ON J.MOB_MTCHED_LYLTY_ID = C.ULPMEMBERSHIPID
        WHERE C.PRIMARY_CUSTOMER = '1'
    ) A
    WHERE RNK = 1
    ;
    """


def build_final_extract_sql(cfg):
    return f"""
    DROP TABLE IF EXISTS {cfg['final_table']};

    CREATE TABLE {cfg['final_table']} AS
    WITH CTE AS (
        SELECT DISTINCT
            x.CARDNO,
            x.TARGET_CONTROL_TAG,
            x.VALID_MOBILE_TAG_F,
            x.ENROLL_STORE,
            t.store_code AS LTS,
            t.city AS LT_City,
            t.state AS LT_State,
            t.region AS LT_Region,
            t.channel AS LT_CHANNEL,
            x.FIRSTNAME,
            x.LASTNAME,
            x.GENDER,
            x.MOBILE,
            x.FINAL_CUTS,
            x.CRCDR AS CAMID,
            '{sql_quote(cfg["campaign_name"])}' AS CAMPAIGNNAME,
            '{sql_quote(cfg["brand_code"])}' AS BRAND,
            y.UCICID
        FROM CARTESIAN_CON.CAMP_ACTIVE_EDW2 x
        INNER JOIN (
            SELECT
                k.ULPMEMBERSHIPID,
                K.UCIC AS UCICID,
                ENROLLMENTSTORECODE
            FROM (
                SELECT
                    c.ULPMEMBERSHIPID,
                    c.SPOUSEDOB,
                    I.UCIC,
                    C.ENROLLMENTSTORECODE,
                    ROW_NUMBER() OVER (
                        PARTITION BY c.ULPMEMBERSHIPID
                        ORDER BY i.bill_date DESC
                    ) AS RNK
                FROM SEM_PU_CUST_ALL.V_TGT_CUST_ALL_UCIC_LYLTY_MAPNG_BI M,
                     SEM_IMC.V_FCT_RTL_C360_TRANSACTION_BI I,
                     SEM_PU_CUST_ALL.V_DIM_PSX_GLD_EDW_ALL_BI C,
                     CARTESIAN_CON.STORE_MASTER_FINAL s
                WHERE i.UCIC = m.UCIC
                  AND i.storecode = s.old_store_code
                  AND m.MOB_MTCHED_LYLTY_ID = c.ULPMEMBERSHIPID
                GROUP BY
                    c.ULPMEMBERSHIPID,
                    s.STORE_CODE,
                    i.bill_date,
                    s.city,
                    s.state,
                    s.region,
                    c.SPOUSEDOB,
                    I.UCIC,
                    C.ENROLLMENTSTORECODE
            ) k
            WHERE k.RNK = 1
            GROUP BY 1,2,3
        ) y
            ON x.CARDNO = y.ULPMEMBERSHIPID
        INNER JOIN {cfg['overall_table']} t
            ON t.MOB_MTCHED_LYLTY_ID = x.CARDNO
        WHERE VALID_MOBILE_TAG_F = 'V'
          AND X.MOBILE NOT IN (
              SELECT DISTINCT MOBILE
              FROM CAMPAIGN_ALL_MEDIUM_BLACKLISTED
              WHERE MOBILE IS NOT NULL
          )
          AND CRCDR = '{sql_quote(cfg["cam_id"])}'
          AND TARGET_CONTROL_TAG = 'N'
        GROUP BY
            1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18
    )
    SELECT *
    FROM CTE
    ;
    """


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.header("🎯 Campaign Setup")

    st.button("🧹 Clear", use_container_width=True, on_click=clear_form)

    st.text_input("CAM ID", key="cam_id")
    st.text_input("Campaign Name", key="campaign_name")

    st.selectbox(
        "Channel",
        ["", "WHATSAPP", "SMS", "RCS"],
        key="mode",
        format_func=lambda x: "Select Channel" if x == "" else x
    )

    st.selectbox(
        "Base Type",
        ["", "ENCIRCLE", "CROSS CHANNEL", "ENCIRCLE + CROSS CHANNEL"],
        key="base_type",
        format_func=lambda x: "Select Base Type" if x == "" else x
    )

    st.subheader("📅 Dates")
    st.date_input("Transaction Start Date", key="txn_start_date")

    st.checkbox(
        "High Value Customer",
        key="enable_high_value_filter"
    )

    if st.session_state.enable_high_value_filter:
        st.number_input(
            "Minimum Bill Value",
            min_value=0,
            step=10000,
            key="high_value_min_bill"
        )

    filter_options = ["City", "Region", "State", "Store Code", "Pincode"]
    base_type_selected = st.session_state.base_type

    st.subheader("✅ Filters")

    if base_type_selected == "ENCIRCLE":
        st.multiselect(
            "Encircle Filter Selection",
            filter_options,
            key="encircle_filter_fields"
        )

        enc_selected = st.session_state.encircle_filter_fields
        if "City" in enc_selected:
            st.text_area("Encircle City", key="encircle_city_text", height=70)
        if "Region" in enc_selected:
            st.text_area("Encircle Region", key="encircle_region_text", height=70)
        if "State" in enc_selected:
            st.text_area("Encircle State", key="encircle_state_text", height=70)
        if "Store Code" in enc_selected:
            st.text_area("Encircle Store Code", key="encircle_store_code_text", height=80)
        if "Pincode" in enc_selected:
            st.text_area("Encircle Pincode", key="encircle_pincode_text", height=80)

    elif base_type_selected == "CROSS CHANNEL":
        st.multiselect(
            "Cross Channel Filter Selection",
            filter_options,
            key="cross_filter_fields"
        )

        cross_selected = st.session_state.cross_filter_fields
        if "City" in cross_selected:
            st.text_area("Cross Channel City", key="cross_city_text", height=70)
        if "Region" in cross_selected:
            st.text_area("Cross Channel Region", key="cross_region_text", height=70)
        if "State" in cross_selected:
            st.text_area("Cross Channel State", key="cross_state_text", height=70)
        if "Store Code" in cross_selected:
            st.text_area("Cross Channel Store Code", key="cross_store_code_text", height=80)
        if "Pincode" in cross_selected:
            st.text_area("Cross Channel Pincode", key="cross_pincode_text", height=80)

    elif base_type_selected == "ENCIRCLE + CROSS CHANNEL":
        st.multiselect(
            "Encircle Specific Filters",
            ["City", "Region", "State", "Store Code", "Pincode"],
            key="encircle_filter_fields"
        )

        enc_selected = st.session_state.encircle_filter_fields
        if "City" in enc_selected:
            st.text_area("Encircle City", key="encircle_city_text", height=70)
        if "Region" in enc_selected:
            st.text_area("Encircle Region", key="encircle_region_text", height=70)
        if "State" in enc_selected:
            st.text_area("Encircle State", key="encircle_state_text", height=70)
        if "Store Code" in enc_selected:
            st.text_area("Encircle Store Code", key="encircle_store_code_text", height=80)
        if "Pincode" in enc_selected:
            st.text_area("Encircle Pincode", key="encircle_pincode_text", height=80)

        st.multiselect(
            "Cross Channel Specific Filters",
            ["City", "Region", "State", "Store Code", "Pincode"],
            key="cross_filter_fields"
        )

        cross_selected = st.session_state.cross_filter_fields
        if "City" in cross_selected:
            st.text_area("Cross Channel City", key="cross_city_text", height=70)
        if "Region" in cross_selected:
            st.text_area("Cross Channel Region", key="cross_region_text", height=70)
        if "State" in cross_selected:
            st.text_area("Cross Channel State", key="cross_state_text", height=70)
        if "Store Code" in cross_selected:
            st.text_area("Cross Channel Store Code", key="cross_store_code_text", height=80)
        if "Pincode" in cross_selected:
            st.text_area("Cross Channel Pincode", key="cross_pincode_text", height=80)

        st.multiselect(
            "Common Filter Selection",
            ["City", "Region", "State", "Store Code", "Pincode"],
            key="common_filter_fields"
        )

        common_selected = st.session_state.common_filter_fields
        if "City" in common_selected:
            st.text_area("City", key="city_text", height=70)
        if "Region" in common_selected:
            st.text_area("Region", key="region_text", height=70)
        if "State" in common_selected:
            st.text_area("State", key="state_text", height=70)
        if "Store Code" in common_selected:
            st.text_area("Common Store Code", key="common_store_code_text", height=80)
        if "Pincode" in common_selected:
            st.text_area("Common Pincode", key="common_pincode_text", height=80)

    st.markdown("---")
    btn_run = st.button("▶️ Run Flow", use_container_width=True)


# ============================================================
# RUNTIME CFG
# ============================================================
filter_lists = get_filter_lists_from_ui()
active_tables = st.session_state.get("active_run_tables", {})

cfg = {
    "db_host": DEFAULTS["db_host"],
    "db_port": DEFAULTS["db_port"],
    "db_name": DEFAULTS["db_name"],
    "db_user": DEFAULTS["db_user"],
    "db_pass": decode_db_password(ENCODED_DB_PASSWORD),

    "cam_id": st.session_state.cam_id,
    "campaign_name": st.session_state.campaign_name,
    "brand_code": DEFAULTS["brand_code"],
    "final_cut": DEFAULTS["final_cut"],
    "mode": st.session_state.mode,
    "base_type": st.session_state.base_type,

    "txn_start_date": st.session_state.txn_start_date.strftime("%Y-%m-%d"),
    "st_dt": DEFAULTS["st_dt"],
    "ed_dt": DEFAULTS["ed_dt"],

    "tsq_table": active_tables.get("tsq_table", ""),
    "cross_table": active_tables.get("cross_table", ""),
    "cross_filtered_table": active_tables.get("cross_filtered_table", ""),
    "overall_table": active_tables.get("overall_table", ""),
    "final_table": active_tables.get("final_table", ""),

    **filter_lists,

    "delimiter": DEFAULTS["delimiter"],
    "export_encoding": DEFAULTS["export_encoding"],
    "preview_limit": DEFAULTS["preview_limit"],

    "enable_high_value_filter": st.session_state.enable_high_value_filter,
    "high_value_min_bill": st.session_state.high_value_min_bill
}


# ============================================================
# TOP SUMMARY
# ============================================================
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(f'<div class="metric-card"><b>Channel</b><br>{cfg["mode"]}</div>', unsafe_allow_html=True)
with m2:
    st.markdown(f'<div class="metric-card"><b>Base Type</b><br>{cfg["base_type"]}</div>', unsafe_allow_html=True)
with m3:
    st.markdown(f'<div class="metric-card"><b>CAM ID</b><br>{cfg["cam_id"]}</div>', unsafe_allow_html=True)
with m4:
    st.markdown(f'<div class="metric-card"><b>Campaign Name</b><br>{cfg["campaign_name"]}</div>', unsafe_allow_html=True)


step_counts_placeholder = st.empty()
final_count_placeholder = st.empty()
preview_area_placeholder = st.empty()


# ============================================================
# RUN FLOW
# ============================================================
if btn_run:
    st.session_state.last_counts = {}
    st.session_state.step_count_rows = []
    st.session_state.download_csv_bytes = None
    st.session_state.download_csv_name = None
    st.session_state.flow_completed = False
    st.session_state.preview_df = None

    run_suffix = make_safe_suffix(st.session_state.cam_id)
    st.session_state.active_run_tables = {
        "tsq_table": f"TBM_TSQ_{run_suffix}",
        "cross_table": f"TBM_CC_{run_suffix}",
        "cross_filtered_table": f"TBM_CC_1_{run_suffix}",
        "overall_table": f"TBM_OVERALL_{run_suffix}",
        "final_table": f"TBM_FINAL_{run_suffix}",
    }

    cfg["tsq_table"] = st.session_state.active_run_tables["tsq_table"]
    cfg["cross_table"] = st.session_state.active_run_tables["cross_table"]
    cfg["cross_filtered_table"] = st.session_state.active_run_tables["cross_filtered_table"]
    cfg["overall_table"] = st.session_state.active_run_tables["overall_table"]
    cfg["final_table"] = st.session_state.active_run_tables["final_table"]

    progress = st.progress(0, text="Running flow...")

    conn = None
    try:
        conn = get_conn(cfg)
        conn.autocommit = False

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            progress.progress(15, text="Running flow...")

            if cfg["base_type"] in {"ENCIRCLE", "ENCIRCLE + CROSS CHANNEL"}:
                execute_sql(cur, build_tsq_sql(cfg))
                conn.commit()

                tsq_cnt = fetch_one(
                    cur,
                    f"""
                    SELECT COUNT(DISTINCT MOB_MTCHED_LYLTY_ID) AS distinct_ids,
                           COUNT(MOB_MTCHED_LYLTY_ID) AS rows
                    FROM {cfg['tsq_table']};
                    """
                )
                tsq_cnt = count_row_to_dict(tsq_cnt)
                append_step_count(cfg["tsq_table"], tsq_cnt["distinct_ids"], tsq_cnt["rows"])
                with step_counts_placeholder.container():
                    render_running_step_counts()
            else:
                execute_sql(
                    cur,
                    f"""
                    DROP TABLE IF EXISTS {cfg['tsq_table']};
                    CREATE TABLE {cfg['tsq_table']} AS
                    SELECT CAST(NULL AS VARCHAR) AS MOB_MTCHED_LYLTY_ID,
                           CAST(NULL AS VARCHAR) AS STATE,
                           CAST(NULL AS VARCHAR) AS REGION,
                           CAST(NULL AS VARCHAR) AS CITY,
                           CAST(NULL AS VARCHAR) AS store_code,
                           CAST(NULL AS VARCHAR) AS channel
                    WHERE 1=0;
                    """
                )
                conn.commit()

            progress.progress(35, text="Running flow...")

            if cfg["base_type"] in {"CROSS CHANNEL", "ENCIRCLE + CROSS CHANNEL"}:
                execute_sql(cur, build_cross_sql(cfg))
                conn.commit()

                cross_cnt = fetch_one(
                    cur,
                    f"""
                    SELECT COUNT(DISTINCT MOB_MTCHED_LYLTY_ID) AS distinct_ids,
                           COUNT(MOB_MTCHED_LYLTY_ID) AS rows
                    FROM {cfg['cross_table']};
                    """
                )
                cross_cnt = count_row_to_dict(cross_cnt)
                append_step_count(cfg["cross_table"], cross_cnt["distinct_ids"], cross_cnt["rows"])
                with step_counts_placeholder.container():
                    render_running_step_counts()

                execute_sql(cur, build_cross_filtered_sql(cfg))
                conn.commit()

                cross_filtered_cnt = fetch_one(
                    cur,
                    f"""
                    SELECT COUNT(DISTINCT MOB_MTCHED_LYLTY_ID) AS distinct_ids,
                           COUNT(MOB_MTCHED_LYLTY_ID) AS rows
                    FROM {cfg['cross_filtered_table']};
                    """
                )
                cross_filtered_cnt = count_row_to_dict(cross_filtered_cnt)
                append_step_count(cfg["cross_filtered_table"], cross_filtered_cnt["distinct_ids"], cross_filtered_cnt["rows"])
                with step_counts_placeholder.container():
                    render_running_step_counts()
            else:
                execute_sql(
                    cur,
                    f"""
                    DROP TABLE IF EXISTS {cfg['cross_table']};
                    CREATE TABLE {cfg['cross_table']} AS
                    SELECT CAST(NULL AS VARCHAR) AS MOB_MTCHED_LYLTY_ID,
                           CAST(NULL AS VARCHAR) AS STATE,
                           CAST(NULL AS VARCHAR) AS REGION,
                           CAST(NULL AS VARCHAR) AS CITY,
                           CAST(NULL AS VARCHAR) AS store_code,
                           CAST(NULL AS VARCHAR) AS channel
                    WHERE 1=0;

                    DROP TABLE IF EXISTS {cfg['cross_filtered_table']};
                    CREATE TABLE {cfg['cross_filtered_table']} AS
                    SELECT * FROM {cfg['cross_table']};
                    """
                )
                conn.commit()

            progress.progress(55, text="Running flow...")

            execute_sql(cur, build_overall_sql(cfg))
            conn.commit()

            overall_cnt = fetch_one(
                cur,
                f"""
                SELECT COUNT(DISTINCT MOB_MTCHED_LYLTY_ID) AS distinct_ids,
                       COUNT(MOB_MTCHED_LYLTY_ID) AS rows
                FROM {cfg['overall_table']};
                """
            )
            overall_cnt = count_row_to_dict(overall_cnt)
            append_step_count(cfg["overall_table"], overall_cnt["distinct_ids"], overall_cnt["rows"])
            with step_counts_placeholder.container():
                render_running_step_counts()

            targetable_distinct = fetch_scalar(
                cur,
                f"""
                SELECT COUNT(DISTINCT A.MOB_MTCHED_LYLTY_ID)
                FROM {cfg['overall_table']} A
                INNER JOIN CARTESIAN_CON.EDW_CAMPAIGNS_VIEW GCT
                    ON GCT.ULPMEMBERSHIPID = A.MOB_MTCHED_LYLTY_ID
                WHERE GCT.edw_global_control_tag = 'N';
                """
            )
            append_step_count("Overall Targetable Distinct", targetable_distinct, None)
            with step_counts_placeholder.container():
                render_running_step_counts()

            progress.progress(70, text="Running flow...")

            execute_sql(cur, build_campaign_load_sql(cfg))
            conn.commit()

            camp_target_rows = fetch_scalar(
                cur,
                f"""
                SELECT COUNT(*)
                FROM cartesian_con.CAMP_ACTIVE_EDW2
                WHERE TARGET_CONTROL_TAG = 'N'
                  AND CRCDR = '{sql_quote(cfg["cam_id"])}';
                """
            )
            append_step_count("CAMP_ACTIVE Target Rows", None, camp_target_rows)
            with step_counts_placeholder.container():
                render_running_step_counts()

            progress.progress(82, text="Running flow...")

            execute_sql(cur, build_final_extract_sql(cfg))
            conn.commit()

        progress.progress(92, text="Running flow...")
        read_conn = get_conn(cfg)
        try:
            with read_conn.cursor(cursor_factory=RealDictCursor) as read_cur:
                final_count_row = fetch_one(
                    read_cur,
                    f"""
                    SELECT COUNT(DISTINCT CARDNO) AS distinct_ids,
                           COUNT(*) AS rows
                    FROM {cfg['final_table']};
                    """
                )
                final_count_row = count_row_to_dict(final_count_row)

                append_step_count(
                    cfg["final_table"],
                    final_count_row["distinct_ids"],
                    final_count_row["rows"]
                )
                with step_counts_placeholder.container():
                    render_running_step_counts()

                st.session_state.download_csv_bytes = resultset_to_cedilla_csv_bytes(
                    read_cur,
                    f"SELECT * FROM {cfg['final_table']};",
                    delimiter=cfg["delimiter"],
                    encoding=cfg["export_encoding"]
                )
                st.session_state.download_csv_name = output_file_name(cfg["cam_id"], cfg["mode"])

            preview_df = pd.read_sql(
                f"SELECT * FROM {cfg['final_table']} LIMIT {int(cfg['preview_limit'])};",
                read_conn
            )
            st.session_state.preview_df = preview_df
            st.session_state.last_counts = {
                "final_distinct_ids": final_count_row["distinct_ids"],
                "final_rows": final_count_row["rows"]
            }
        finally:
            read_conn.close()

        progress.progress(100, text="Flow finished successfully.")
        st.success("✅ Flow finished successfully")

        step_counts_placeholder.empty()

        with final_count_placeholder.container():
            render_final_count_card(
                st.session_state.last_counts.get("final_distinct_ids"),
                st.session_state.last_counts.get("final_rows")
            )

        st.session_state.flow_completed = True

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        st.error(f"❌ Pipeline failed: {e}")

    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ============================================================
# POST-RUN PREVIEW + DOWNLOAD
# ============================================================
if st.session_state.get("flow_completed"):
    with preview_area_placeholder.container():
        if st.session_state.get("preview_df") is not None:
            st.subheader("👀 Preview Table")
            st.dataframe(
                st.session_state.preview_df.head(20),
                use_container_width=True,
                hide_index=True,
                height=220
            )

        if st.session_state.get("download_csv_bytes") is not None:
            st.download_button(
                label=f"⬇️ Download Cedilla CSV ({st.session_state.get('download_csv_name')})",
                data=st.session_state.get("download_csv_bytes"),
                file_name=st.session_state.get("download_csv_name"),
                mime="text/csv",
                use_container_width=True,
                key="download_csv_final"
            )