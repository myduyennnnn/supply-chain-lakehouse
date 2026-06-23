"""
Late Delivery Risk Prediction — Combined ML Page

5 tab:
  1. Single Prediction   — nhập tay từng trường → xác suất + SHAP waterfall
  2. Batch Prediction    — upload CSV nhiều đơn → threshold điều chỉnh → danh sách rủi ro
  3. Model Benchmarks    — so sánh 5 model
  4. Global Risk Drivers — SHAP summary trên test set
  5. ML Registry         — MLflow experiment history, production model info
"""

import io
import os
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import boto3
import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import shap
import streamlit as st

warnings.filterwarnings("ignore")

# ── MLflow (optional — graceful fallback nếu server down) ─────────────────────
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml_app"))
try:
    from mlflow_setup import TRACKING_URI, EXPERIMENT_NAME, MODEL_NAME
    from mlflow.tracking import MlflowClient
    _MLFLOW_OK = True
except ImportError:
    _MLFLOW_OK = False
    TRACKING_URI = "http://localhost:5000"
    MODEL_NAME   = "delivery-risk-model"
    EXPERIMENT_NAME = "delivery-risk-prediction"

MODEL_DIR = Path(__file__).parent.parent.parent / "ml_app" / "ml_model"

# ── Categorical options (DataCo Supply Chain dataset) ─────────────────────────
_CAT_OPTIONS: dict[str, list[str]] = {
    "shipping_mode":    ["Standard Class", "Second Class", "First Class", "Same Day"],
    "market":           ["Europe", "LATAM", "Pacific Asia", "USCA", "Africa"],
    "payment_type":     ["DEBIT", "TRANSFER", "PAYMENT", "CASH"],
    "customer_segment": ["Consumer", "Corporate", "Home Office"],
    "order_region": [
        "Western Europe", "Central America", "Oceania", "Eastern Asia",
        "South America", "Eastern Europe", "Caribbean", "Southeast Asia",
        "West Africa", "Southern Africa", "Northern Africa",
        "Central Asia", "Southern Asia", "North America",
    ],
    "category_name": [
        "Fitness", "Outdoors", "Cleats", "Men's Footwear", "Women's Apparel",
        "Indoor/Outdoor Games", "Cameras", "Boxing & MMA", "Golf Balls",
        "Hunting & Shooting", "Computers", "Sporting Goods",
    ],
    "department_name": ["Fan Shop", "Fitness", "Apparel", "Golf", "Outdoors", "Footwear", "Technology"],
    "order_country": [
        "United States", "France", "Mexico", "Australia", "Germany",
        "Brazil", "United Kingdom", "Nigeria", "India", "China",
    ],
    "customer_country": [
        "United States", "Puerto Rico", "Australia", "France",
        "Germany", "United Kingdom", "Nigeria", "India",
    ],
}

_NUM_DEFAULTS: dict[str, float] = {
    "days_scheduled": 4, "is_weekend": 0, "order_month": 6,
    "order_quarter": 2, "ship_day_of_week": 2, "profit_margin": 0.10,
    "unit_price": 50.0, "is_urgent_shipping": 0, "order_item_quantity": 2,
    "order_item_product_price": 100.0, "order_item_discount_rate": 0.05,
    "order_item_discount_amount": 5.0, "sales": 95.0,
    "order_item_total": 190.0, "order_item_profit_ratio": 0.10, "order_profit": 10.0,
}

_NUM_RANGES: dict[str, tuple] = {
    "days_scheduled": (0, 30, 1), "order_month": (1, 12, 1),
    "order_quarter": (1, 4, 1), "ship_day_of_week": (0, 6, 1),
    "order_item_quantity": (1, 100, 1), "order_item_discount_rate": (0.0, 1.0, 0.01),
    "order_item_product_price": (0.0, 2000.0, 1.0), "order_item_discount_amount": (0.0, 500.0, 0.1),
    "sales": (0.0, 5000.0, 1.0), "order_item_total": (0.0, 5000.0, 1.0),
    "order_item_profit_ratio": (-1.0, 1.0, 0.01), "order_profit": (-500.0, 1000.0, 0.1),
    "profit_margin": (-1.0, 2.0, 0.01), "unit_price": (0.0, 2000.0, 1.0),
}

_BINARY_FEATS = {"is_weekend", "is_urgent_shipping", "is_actual_late"}

ML_THEME = ["#6F42C1", "#007BFF", "#00CCCC", "#0DCAF0", "#17A2B8", "#8A5EDB", "#3395FF"]


# ── Artifact loading ──────────────────────────────────────────────────────────
def _r2_buf(fname: str) -> io.BytesIO:
    """Download một file từ R2 vào memory buffer."""
    s3 = boto3.client(
        "s3",
        endpoint_url=os.getenv("R2_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
    )
    buf = io.BytesIO()
    s3.download_fileobj(os.getenv("R2_BUCKET_NAME", "supply-chain-ai-native"), f"ml_model/{fname}", buf)
    buf.seek(0)
    return buf


def _open(fname: str):
    """Trả về local Path nếu tồn tại, ngược lại download từ R2."""
    local = MODEL_DIR / fname
    return local if local.exists() else _r2_buf(fname)


@st.cache_resource
def _load_artifacts() -> dict:
    return {
        "model":        joblib.load(_open("best_model.pkl")),
        "preprocessor": joblib.load(_open("preprocessor.pkl")),
        "sel_feats":    joblib.load(_open("selected_features.pkl")),
        "all_feats":    list(joblib.load(_open("all_original_features.pkl"))),
        "X_test":       joblib.load(_open("X_test_p.pkl")),
        "results":      pd.read_csv(_open("results.csv")).sort_values("F1-Score", ascending=False).reset_index(drop=True),
    }


# ── Single prediction (via preprocessor — nhận raw values) ────────────────────
def _predict_single(art: dict, user_input: dict) -> tuple[float, np.ndarray]:
    pre   = art["preprocessor"]
    num_f = list(pre.transformers_[0][2])
    cat_f = list(pre.transformers_[1][2])

    full_row = {f: user_input.get(f, np.nan)      for f in num_f}
    full_row.update({f: user_input.get(f, "Unknown") for f in cat_f})

    X_trans = pre.transform(pd.DataFrame([full_row]))
    idx     = [art["all_feats"].index(f) for f in art["sel_feats"] if f in art["all_feats"]]
    X_sel   = X_trans[:, idx]
    return float(art["model"].predict_proba(X_sel)[0, 1]), X_sel


# ── Batch prediction (CSV raw → preprocessor → model) ────────────────────────
def _predict_batch(art: dict, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    Nhận DataFrame raw (cột num + cat giống template),
    chạy qua preprocessor → feature selection → model.
    """
    pre   = art["preprocessor"]
    num_f = list(pre.transformers_[0][2])
    cat_f = list(pre.transformers_[1][2])

    full = pd.DataFrame(index=df.index)
    for f in num_f:
        full[f] = pd.to_numeric(df[f], errors="coerce") if f in df.columns else np.nan
    for f in cat_f:
        full[f] = df[f].astype(str) if f in df.columns else "Unknown"

    X_trans = pre.transform(full)
    idx     = [art["all_feats"].index(f) for f in art["sel_feats"] if f in art["all_feats"]]
    X_sel   = X_trans[:, idx]
    proba   = art["model"].predict_proba(X_sel)[:, 1]
    return proba, X_sel


# ── SHAP helpers ──────────────────────────────────────────────────────────────
def _get_explainer(model, X_ref):
    if hasattr(model, "feature_importances_"):
        return shap.TreeExplainer(model)
    if hasattr(model, "coef_"):
        return shap.LinearExplainer(model, X_ref)
    return shap.KernelExplainer(model.predict_proba, shap.sample(X_ref, 100))


def _shap_waterfall_fig(model, X_sel: np.ndarray, feats: list, idx: int = 0) -> plt.Figure:
    exp  = _get_explainer(model, X_sel)
    vals = exp.shap_values(X_sel)
    if isinstance(vals, list):
        vals, base = vals[1], exp.expected_value[1]
    else:
        base = exp.expected_value
    fig, _ = plt.subplots(figsize=(7, 3.5))
    shap.waterfall_plot(
        shap.Explanation(values=vals[idx], base_values=base,
                         data=X_sel[idx], feature_names=list(feats)),
        max_display=8, show=False,
    )
    plt.tight_layout()
    return fig


@st.cache_resource
def _shap_global_data(_key: str):
    art    = _load_artifacts()
    model  = art["model"]
    sample = art["X_test"][: min(500, len(art["X_test"]))]
    exp    = _get_explainer(model, sample)
    vals   = exp.shap_values(sample)
    if isinstance(vals, list):
        vals = vals[1]
    return vals, sample, list(art["sel_feats"])


# ── Form builder (single prediction) ─────────────────────────────────────────
def _build_form(art: dict) -> dict:
    pre     = art["preprocessor"]
    sel     = art["sel_feats"]
    num_set = set(pre.transformers_[0][2])
    cat_set = set(pre.transformers_[1][2])
    num_sel = [f for f in sel if f in num_set]
    cat_sel = [f for f in sel if f in cat_set]

    user_input: dict = {}
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("##### Numeric Features")
        for feat in num_sel:
            default = _NUM_DEFAULTS.get(feat, 0.0)
            if feat in _BINARY_FEATS:
                val = st.radio(feat, [0, 1], index=int(default), horizontal=True, key=f"s_{feat}")
            elif feat in _NUM_RANGES:
                lo, hi, step = _NUM_RANGES[feat]
                val = st.slider(feat, min_value=lo, max_value=hi,
                                value=type(lo)(default), step=step, key=f"s_{feat}",
                                format="%d" if isinstance(step, int) else "%.2f")
            else:
                val = st.number_input(feat, value=float(default), format="%.4f", key=f"s_{feat}")
            user_input[feat] = val

    with col_r:
        st.markdown("##### Categorical Features")
        for feat in cat_sel:
            opts = _CAT_OPTIONS.get(feat)
            val  = st.selectbox(feat, opts, key=f"s_{feat}") if opts else \
                   st.text_input(feat, value="Unknown", key=f"s_{feat}")
            user_input[feat] = val

    return user_input


# ── Plotly theme helper ───────────────────────────────────────────────────────
def _theme(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#8A8FA8",
        title_font_color="#1E2243",
        title_font_size=16,
        title_font_family="'Outfit', sans-serif",
        margin=dict(l=16, r=16, t=50, b=16),
        xaxis=dict(gridcolor="#EEECf8", zerolinecolor="#EEECf8", showgrid=True),
        yaxis=dict(gridcolor="#EEECf8", zerolinecolor="#EEECf8", showgrid=True),
        legend=dict(bgcolor="rgba(255,255,255,0.75)", bordercolor="#E4E8F5", borderwidth=1),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# PAGE
# ─────────────────────────────────────────────────────────────────────────────

st.html("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&display=swap');

    /* ── Base ── */
    .stApp {
        background: linear-gradient(155deg, #F3EFFF 0%, #ECF4FF 50%, #E6FDFC 100%) !important;
        font-family: 'Outfit', sans-serif !important;
        color: #1E2243 !important;
    }

    /* ── Title ── */
    .ml-title {
        font-size: 2.8rem;
        font-weight: 900;
        background: linear-gradient(90deg, #6F42C1 0%, #007BFF 55%, #00CCCC 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.5px;
        margin-bottom: 2.5rem;
    }

    /* ── Section Headers ── */
    .section-header {
        font-size: 0.8rem;
        font-weight: 800;
        color: #6F42C1;
        text-transform: uppercase;
        letter-spacing: 2.5px;
        margin: 2.5rem 0 1.5rem;
        padding-left: 14px;
        border-left: 4px solid #007BFF;
    }

    /* ── KPI Cards ── */
    [data-testid="stMetric"] {
        border-radius: 20px;
        padding: 28px 22px;
        border: none !important;
        box-shadow: 0 10px 32px rgba(111,66,193,0.18), 0 2px 8px rgba(0,0,0,0.06);
        overflow: hidden;
        position: relative;
        transition: transform 0.25s ease, box-shadow 0.25s ease;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-7px);
        box-shadow: 0 20px 48px rgba(111,66,193,0.26), 0 6px 16px rgba(0,0,0,0.09);
    }
    [data-testid="stMetric"]::after {
        content: '';
        position: absolute;
        width: 170px; height: 170px;
        border-radius: 50%;
        background: rgba(255,255,255,0.13);
        top: -60px; right: -45px;
        pointer-events: none;
    }

    [data-testid="stMetricValue"] {
        color: #fff !important;
        font-size: 2.3rem !important;
        font-weight: 800 !important;
        position: relative; z-index: 2;
    }
    [data-testid="stMetricLabel"] {
        color: rgba(255,255,255,0.88) !important;
        font-size: 0.78rem !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        letter-spacing: 1.4px;
        position: relative; z-index: 2;
    }

    /* Column gradients — Purple / Blue / Teal / Cyan / Violet */
    [data-testid="column"]:nth-child(1) [data-testid="stMetric"] {
        background: linear-gradient(140deg, #9B6AE0 0%, #6F42C1 100%);
    }
    [data-testid="column"]:nth-child(2) [data-testid="stMetric"] {
        background: linear-gradient(140deg, #4AAAFF 0%, #007BFF 100%);
    }
    [data-testid="column"]:nth-child(3) [data-testid="stMetric"] {
        background: linear-gradient(140deg, #33E0E0 0%, #00CCCC 100%);
    }
    [data-testid="column"]:nth-child(4) [data-testid="stMetric"] {
        background: linear-gradient(140deg, #30D6F5 0%, #17A2B8 100%);
    }
    [data-testid="column"]:nth-child(5) [data-testid="stMetric"] {
        background: linear-gradient(140deg, #A07EE8 0%, #8A5EDB 100%);
    }

    /* ── Divider ── */
    hr {
        border: none !important;
        height: 2px !important;
        background: linear-gradient(90deg, #6F42C1, #007BFF, #00CCCC) !important;
        opacity: 0.28 !important;
        margin: 3rem 0 !important;
    }

    /* ── Risk Cards ── */
    .risk-card { border-radius: 16px; padding: 24px; text-align: center; margin: 12px 0; }
    .risk-high  { background: rgba(204,34,34,0.08); border: 2px solid #cc2222; }
    .risk-low   { background: rgba(0,204,204,0.08); border: 2px solid #00CCCC; }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        border-bottom: 2px solid #E4E8F5;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border: none;
        padding: 10px 24px 12px;
        color: #8A8FA8;
        font-weight: 700;
        font-size: 1rem;
        border-radius: 10px 10px 0 0;
        transition: color 0.2s ease;
    }
    .stTabs [data-baseweb="tab"]:hover { color: #6F42C1; }
    .stTabs [aria-selected="true"] {
        color: #6F42C1 !important;
        border-bottom: 3px solid #6F42C1 !important;
        background: rgba(111,66,193,0.07) !important;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(175deg, #1C1050 0%, #0A061F 100%) !important;
    }
    [data-testid="stSidebar"] label { color: #ffffff !important; }
    [data-testid="stSidebarContent"] { color: #ffffff !important; }
    [data-testid="stSidebarContent"] * { color: #ffffff !important; }

    /* ── Dataframe ── */
    [data-testid="stDataFrame"] {
        border-radius: 16px !important;
        overflow: hidden !important;
        box-shadow: 0 8px 28px rgba(111,66,193,0.12), 0 2px 8px rgba(0,0,0,0.05) !important;
        border: 1px solid #E4E8F5 !important;
    }

    /* ── Captions ── */
    .stCaption p { color: #8A8FA8 !important; font-style: italic; }

    p { color: #1E2243; }
</style>
""")

st.markdown('<div class="ml-title">Late Delivery Risk Prediction</div>', unsafe_allow_html=True)

try:
    art   = _load_artifacts()
    model = art["model"]
    best  = art["results"].iloc[0]
except Exception as _e:
    st.error(
        f"Không thể tải ML artifacts: `{_e}`\n\n"
        "**Local:** chạy `python orchestration/pipeline.py --gold-only --with-ml`\n\n"
        "**Cloud:** chạy `python scripts/push_lakehouse.py` để upload lên R2 trước."
    )
    st.stop()

st.caption(
    f"Best model: **{best['Model']}** — AUC {best['AUC']:.3f} | F1 {best['F1-Score']:.3f} "
    f"({len(art['sel_feats'])} features)"
)

tab_single, tab_batch, tab_bench, tab_shap, tab_registry = st.tabs([
    "Single Prediction", "Batch Prediction", "Model Benchmarks",
    "Global Risk Drivers", "ML Registry",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Single Prediction
# ══════════════════════════════════════════════════════════════════════════════
with tab_single:
    st.markdown("Nhập thông tin đơn hàng để dự đoán nguy cơ giao trễ.")

    with st.form("single_form"):
        user_input = _build_form(art)
        submitted  = st.form_submit_button("Predict Risk", type="primary", use_container_width=True)

    if submitted:
        prob, X_sel = _predict_single(art, user_input)
        is_late = prob >= 0.5
        label   = "HIGH RISK — Predicted Late" if is_late else "LOW RISK — On Time"
        color   = "#cc2222" if is_late else "#00CCCC"
        card    = "risk-high" if is_late else "risk-low"

        st.markdown(f"""
        <div class="risk-card {card}">
            <div style="font-size:1.4rem;font-weight:700;color:{color};">{label}</div>
            <div style="font-size:2.8rem;font-weight:900;color:{color};">{prob:.1%}</div>
            <div style="color:#8A8FA8;font-size:0.85rem;">Xác suất giao hàng trễ</div>
        </div>
        """, unsafe_allow_html=True)

        m1, m2, m3 = st.columns(3)
        m1.metric("Probability", f"{prob:.3f}")
        m2.metric("Prediction",  "Late" if is_late else "On Time")
        m3.metric("Threshold",   "0.500")

        st.markdown("**Root Cause — SHAP Waterfall**")
        try:
            fig = _shap_waterfall_fig(model, X_sel, art["sel_feats"])
            st.pyplot(fig, use_container_width=True)
            plt.clf()
        except Exception as e:
            st.warning(f"SHAP: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Batch Prediction
# ══════════════════════════════════════════════════════════════════════════════
with tab_batch:

    # ── Threshold control ──────────────────────────────────────────────────────
    st.markdown("#### Risk Threshold")
    st.caption(
        "Giảm threshold → nhạy hơn (bắt nhiều late hơn, có thể false positive). "
        "Tăng → chính xác hơn nhưng có thể bỏ sót. "
        "Chi phí bỏ sót thường **cao hơn** chi phí cảnh báo nhầm."
    )
    threshold = st.slider(
        "Threshold", min_value=0.05, max_value=0.95, value=0.5, step=0.01,
        format="%.2f", key="batch_threshold",
        help="Đơn có prob_late ≥ threshold → HIGH RISK",
    )

    st.divider()

    # ── Upload ─────────────────────────────────────────────────────────────────
    st.markdown("#### Upload Đơn Hàng")

    # Template download — dùng num_f + cat_f của preprocessor (input thô cho người dùng)
    _pre_b    = art["preprocessor"]
    _num_f_b  = list(_pre_b.transformers_[0][2])
    _cat_f_b  = list(_pre_b.transformers_[1][2])
    _tmpl_cols = _num_f_b + _cat_f_b
    st.download_button(
        "Download CSV Template",
        data=pd.DataFrame(columns=_tmpl_cols).to_csv(index=False).encode("utf-8"),
        file_name="order_template.csv",
        mime="text/csv",
        help=f"Điền giá trị thô: numeric cho {len(_num_f_b)} cột số, chuỗi cho {len(_cat_f_b)} cột categorical.",
    )

    uploaded = st.file_uploader(
        f"Upload CSV ({len(_tmpl_cols)} cột theo template — numeric + categorical thô)",
        type=["csv"],
        key="batch_upload",
    )

    _batch_keys = ["batch_proba", "batch_df", "batch_X", "batch_shap_sv", "batch_shap_base", "batch_file_id"]
    for _k in _batch_keys:
        if _k not in st.session_state:
            st.session_state[_k] = None

    if uploaded is not None:
        # Track by name+size to avoid re-running SHAP on every threshold slider change
        file_id = f"{uploaded.name}_{uploaded.size}"

        if st.session_state.batch_file_id != file_id:
            try:
                df_up   = pd.read_csv(uploaded)
                # Chỉ cần ít nhất 1 cột của preprocessor có mặt; cột thiếu được fill NaN/Unknown
                missing = set(_tmpl_cols) - set(df_up.columns)

                if len(missing) == len(_tmpl_cols):
                    st.error(f"CSV không khớp template — thiếu toàn bộ {len(_tmpl_cols)} cột.")
                elif missing:
                    st.info(f"CSV thiếu {len(missing)} cột — sẽ dùng giá trị mặc định (0 / 'Unknown').")
                if len(missing) < len(_tmpl_cols):
                    with st.spinner("Đang phân tích và tính SHAP..."):
                        proba, X_batch = _predict_batch(art, df_up)

                        exp_b = _get_explainer(model, X_batch)
                        sv_b  = exp_b.shap_values(X_batch)
                        if isinstance(sv_b, list):
                            sv_b, base_b = sv_b[1], exp_b.expected_value[1]
                        else:
                            base_b = exp_b.expected_value

                    st.session_state.batch_proba     = proba
                    st.session_state.batch_df        = df_up.copy()
                    st.session_state.batch_X         = X_batch
                    st.session_state.batch_shap_sv   = sv_b
                    st.session_state.batch_shap_base = base_b
                    st.session_state.batch_file_id   = file_id
                    st.success(f"Đã xử lý {len(df_up)} đơn hàng.")

            except Exception as e:
                st.error(f"Lỗi: {e}")

    # ── Results ────────────────────────────────────────────────────────────────
    if st.session_state.batch_proba is not None:
        proba  = st.session_state.batch_proba
        df_up  = st.session_state.batch_df.copy()
        X_b    = st.session_state.batch_X
        sv_b   = st.session_state.batch_shap_sv
        base_b = st.session_state.batch_shap_base

        # Apply threshold realtime
        df_up["prob_late"]      = proba
        df_up["predicted_late"] = (proba >= threshold).astype(int)

        st.divider()
        st.markdown("#### Kết Quả")

        total     = len(df_up)
        n_late    = int(df_up["predicted_late"].sum())
        n_ok      = total - n_late
        late_rate = n_late / total * 100

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tổng đơn",         total)
        c2.metric("Nguy cơ trễ",      n_late,    delta=f"{late_rate:.1f}%", delta_color="inverse")
        c3.metric("Đúng hạn",         n_ok)
        c4.metric("Threshold",        f"{threshold:.2f}")

        fig_dist = px.histogram(
            df_up, x="prob_late", nbins=20,
            title="Phân phối xác suất trễ",
            color_discrete_sequence=[ML_THEME[0]],
        )
        fig_dist.add_vline(x=threshold, line_dash="dash", line_color="#cc2222",
                           annotation_text=f"Threshold {threshold:.2f}")
        st.plotly_chart(_theme(fig_dist), use_container_width=True)

        # Download
        export = df_up.to_csv(index=False).encode("utf-8")
        st.download_button("Download kết quả (.csv)", data=export,
                           file_name="risk_predictions.csv", mime="text/csv")

        # Filter + table
        show_late = st.checkbox("Chỉ hiện đơn HIGH RISK", value=True, key="show_late")
        df_show   = df_up.sort_values("prob_late", ascending=False)
        if show_late:
            df_show = df_show[df_show["predicted_late"] == 1]

        st.caption(f"Hiển thị {min(50, len(df_show))} đơn — sắp xếp theo xác suất giảm dần.")

        if df_show.empty:
            st.success("Không có đơn nào vượt threshold. Thử giảm threshold.")
        else:
            for i in range(min(50, len(df_show))):
                real_idx  = df_show.index[i]
                row       = df_show.iloc[i]
                prob      = row["prob_late"]
                is_late   = row["predicted_late"] == 1
                badge     = "⚠ HIGH RISK" if is_late else "✓ LOW RISK"
                expanded  = is_late and i < 5

                with st.expander(f"Đơn #{real_idx} | {badge} | Prob: {prob:.1%}", expanded=expanded):
                    bg  = "rgba(204,34,34,0.06)"  if is_late else "rgba(0,204,204,0.06)"
                    clr = "#cc2222"               if is_late else "#007755"
                    st.dataframe(
                        pd.DataFrame(row).T
                          .style.set_properties(**{"background-color": bg, "color": clr}),
                        use_container_width=True,
                    )

                    if is_late:
                        col_s, col_a = st.columns([1.5, 1])
                        with col_s:
                            st.caption("Nguyên nhân (SHAP)")
                            try:
                                fig_w, _ = plt.subplots(figsize=(5, 2.5))
                                shap.waterfall_plot(
                                    shap.Explanation(
                                        values       = sv_b[real_idx],
                                        base_values  = base_b,
                                        data         = X_b[real_idx],
                                        feature_names= list(art["sel_feats"]),
                                    ),
                                    max_display=5, show=False,
                                )
                                plt.tight_layout()
                                st.pyplot(plt.gcf())
                                plt.clf()
                            except Exception as e:
                                st.warning(f"SHAP: {e}")
                        with col_a:
                            st.caption("Gợi ý")
                            st.warning(
                                "**Cần can thiệp:**\n\n"
                                "- Kiểm tra nhà cung cấp / kho\n"
                                "- Xem xét nâng cấp shipping mode\n"
                                "- Thông báo sớm cho khách hàng"
                            )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Model Benchmarks
# ══════════════════════════════════════════════════════════════════════════════
with tab_bench:
    st.markdown("### Model Performance Comparison")
    metrics = ["Accuracy", "Precision", "Recall", "F1-Score", "AUC"]
    st.dataframe(
        art["results"].style.highlight_max(axis=0, subset=metrics, color="#EEECf8"),
        use_container_width=True, hide_index=True,
    )
    fig_b = px.bar(
        art["results"], x="Model", y=metrics, barmode="group", height=380,
        color_discrete_sequence=ML_THEME,
    )
    st.plotly_chart(_theme(fig_b), use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Global SHAP
# ══════════════════════════════════════════════════════════════════════════════
with tab_shap:
    st.markdown("### Global Risk Drivers")

    # ── Feature Importance (XGBoost built-in) ─────────────────────────────────
    if hasattr(model, "feature_importances_"):
        st.markdown('<div class="section-header">Feature Importance — XGBoost</div>', unsafe_allow_html=True)
        st.caption("Mức độ đóng góp của từng feature khi model ra quyết định (gain importance).")

        fi_df = (
            pd.DataFrame({"feature": art["sel_feats"], "importance": model.feature_importances_})
            .sort_values("importance", ascending=True)
            .tail(20)
        )
        fig_fi = px.bar(
            fi_df, x="importance", y="feature", orientation="h",
            title=f"Top {len(fi_df)} Feature Importance ({best['Model']})",
            color="importance", color_continuous_scale=["#0DCAF0", "#007BFF", "#6F42C1"],
        )
        fig_fi.update_layout(coloraxis_showscale=False, yaxis_title="", xaxis_title="Importance Score")
        st.plotly_chart(_theme(fig_fi), use_container_width=True)

        st.divider()

    # ── SHAP Summary ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">SHAP Summary</div>', unsafe_allow_html=True)
    st.caption("SHAP summary trên 500 test samples. Đỏ = feature value cao, xanh = thấp.")
    try:
        sv_g, X_g, feats_g = _shap_global_data(best["Model"])
        fig_g, _ = plt.subplots(figsize=(8, 5))
        shap.summary_plot(sv_g, X_g, feature_names=feats_g, max_display=12, show=False)
        plt.tight_layout()
        st.pyplot(fig_g, use_container_width=True)
        plt.clf()
    except Exception as e:
        st.warning(f"Không thể render SHAP global: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — ML Registry
# ══════════════════════════════════════════════════════════════════════════════
with tab_registry:
    st.markdown("### MLflow Model Registry")
    st.caption(
        f"Tracking server: `{TRACKING_URI}` | "
        f"Experiment: `{EXPERIMENT_NAME}` | "
        f"Model: `{MODEL_NAME}`"
    )

    if not _MLFLOW_OK:
        st.warning("mlflow chưa được install. Chạy: `pip install mlflow`")
        st.stop()

    # ── Helper: load MLflow data (cached 60s) ──────────────────────────────
    @st.cache_data(ttl=60, show_spinner=False)
    def _fetch_registry_data():
        try:
            client = MlflowClient(tracking_uri=TRACKING_URI)

            # Production model (alias "production")
            prod_info = None
            try:
                prod_mv   = client.get_model_version_by_alias(MODEL_NAME, "production")
                prod_run  = client.get_run(prod_mv.run_id)
                prod_info = {
                    "version":    prod_mv.version,
                    "run_id":     prod_mv.run_id,
                    "created_at": datetime.fromtimestamp(
                        prod_mv.creation_timestamp / 1000, tz=timezone.utc
                    ).strftime("%Y-%m-%d %H:%M UTC"),
                    "metrics":    prod_run.data.metrics,
                    "tags":       prod_run.data.tags,
                    "params":     prod_run.data.params,
                }
            except Exception:
                pass  # Chua co alias production

            # Lich su experiments (50 runs gan nhat)
            import mlflow
            mlflow.set_tracking_uri(TRACKING_URI)
            exp = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
            runs_df = pd.DataFrame()
            if exp:
                runs = mlflow.search_runs(
                    experiment_ids=[exp.experiment_id],
                    order_by=["start_time DESC"],
                    max_results=50,
                )
                if not runs.empty:
                    keep = ["run_id", "start_time", "status",
                            "tags.best_model_name",
                            "params.n_features_selected", "params.train_rows",
                            "metrics.best_f1", "metrics.best_auc",
                            "metrics.best_accuracy", "metrics.best_recall"]
                    runs_df = runs[[c for c in keep if c in runs.columns]].copy()
                    runs_df = runs_df.rename(columns={
                        "tags.best_model_name":       "best_model",
                        "params.n_features_selected": "features",
                        "params.train_rows":          "train_rows",
                        "metrics.best_f1":            "F1",
                        "metrics.best_auc":           "AUC",
                        "metrics.best_accuracy":      "Accuracy",
                        "metrics.best_recall":        "Recall",
                    })
                    runs_df["start_time"] = pd.to_datetime(
                        runs_df["start_time"], utc=True
                    ).dt.strftime("%Y-%m-%d %H:%M")

            return prod_info, runs_df, None

        except Exception as exc:
            return None, pd.DataFrame(), str(exc)

    prod_info, runs_df, err = _fetch_registry_data()

    if err:
        st.error(f"Không kết nối được MLflow server: `{err}`")
        st.info(
            "Khởi động server trước khi xem tab này:\n\n"
            "```powershell\n.\\scripts\\start_mlflow_server.ps1\n```"
        )
    else:
        # ── Production model card ──────────────────────────────────────────
        st.markdown("#### Production Model")
        if prod_info:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Version",  f"v{prod_info['version']}")
            c2.metric("F1-Score", f"{prod_info['metrics'].get('best_f1', 0):.4f}")
            c3.metric("AUC",      f"{prod_info['metrics'].get('best_auc', 0):.4f}")
            c4.metric("Accuracy", f"{prod_info['metrics'].get('best_accuracy', 0):.4f}")
            c5.metric("Recall",   f"{prod_info['metrics'].get('best_recall', 0):.4f}")

            with st.expander("Chi tiết run", expanded=False):
                col_l, col_r = st.columns(2)
                with col_l:
                    st.markdown("**Thông tin**")
                    st.write({
                        "Run ID":      prod_info["run_id"][:12] + "...",
                        "Trained at":  prod_info["created_at"],
                        "Best model":  prod_info["tags"].get("best_model_name", "—"),
                        "Data source": prod_info["tags"].get("data_source", "—"),
                    })
                with col_r:
                    st.markdown("**Params**")
                    st.write({k: v for k, v in prod_info["params"].items()})
        else:
            st.info(
                "Chưa có model nào được gán alias 'production'.\n\n"
                "Chạy pipeline với `--with-ml` để train và promote tự động:\n\n"
                "```bash\npython orchestration/pipeline.py --gold-only --with-ml\n```"
            )

        st.divider()

        # ── Experiment run history ─────────────────────────────────────────
        st.markdown("#### Experiment History")
        if runs_df.empty:
            st.info("Chưa có run nào được log. Chạy train_model.py để bắt đầu.")
        else:
            # Metrics trend chart
            numeric_cols = [c for c in ["F1", "AUC", "Accuracy", "Recall"]
                            if c in runs_df.columns]
            if numeric_cols and "start_time" in runs_df.columns:
                plot_df = runs_df[["start_time"] + numeric_cols].dropna().copy()
                plot_df[numeric_cols] = plot_df[numeric_cols].apply(pd.to_numeric, errors="coerce")
                plot_df = plot_df.sort_values("start_time")

                fig_trend = px.line(
                    plot_df, x="start_time", y=numeric_cols,
                    title="Metrics theo thời gian",
                    markers=True, height=320,
                    color_discrete_sequence=ML_THEME,
                )
                st.plotly_chart(_theme(fig_trend), use_container_width=True)

            # Run table
            st.dataframe(
                runs_df.drop(columns=["run_id"], errors="ignore"),
                use_container_width=True,
                hide_index=True,
            )

            st.caption(
                f"Showing {len(runs_df)} recent runs. "
                f"Full UI: [{TRACKING_URI}]({TRACKING_URI})"
            )
