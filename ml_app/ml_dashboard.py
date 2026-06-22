import streamlit as st
import pandas as pd
import numpy as np
import joblib
import shap
import matplotlib.pyplot as plt
import plotly.express as px
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')

st.set_page_config(layout="wide")
st.title("Supply Chain – Late Delivery Risk Management Platform")

MODEL_DIR = Path(r"D:\DWH\supply-chain-lakehouse\ml_app\ml_model")

@st.cache_resource
def load_objects():
    model = joblib.load(MODEL_DIR / 'best_model.pkl')
    preprocessor = joblib.load(MODEL_DIR / 'preprocessor.pkl') 
    all_features = joblib.load(MODEL_DIR / 'all_original_features.pkl') 
    selected_features = joblib.load(MODEL_DIR / 'selected_features.pkl')
    X_test = joblib.load(MODEL_DIR / 'X_test_p.pkl')
    results = pd.read_csv(MODEL_DIR / 'results.csv')
    return model, preprocessor, all_features, selected_features, X_test, results

try:
    model, preprocessor, all_features, selected_features, X_test, results = load_objects()
except FileNotFoundError as e:
    st.error(f"Không tìm thấy file: {e.filename}. Vui lòng chạy file train_model.py trước.")
    st.stop()

if hasattr(model, 'feature_importances_'):
    imp = model.feature_importances_
elif hasattr(model, 'coef_'):
    imp = np.abs(model.coef_[0])
else:
    imp = np.ones(len(selected_features))

feature_importance_df = pd.DataFrame({
    'Feature': selected_features,
    'Importance': imp
}).sort_values('Importance', ascending=True)

st.header("1. Model Performance Benchmark")

st.dataframe(results.style.highlight_max(axis=0, subset=['Accuracy', 'Precision', 'Recall', 'F1-Score', 'AUC'], color='#d4edda'), width=800)

fig_bench = px.bar(results, x='Model', y=['Accuracy', 'Precision', 'Recall', 'F1-Score', 'AUC'], 
             barmode='group', height=400)
fig_bench.update_layout(legend_title_text='Metrics', yaxis_title="Score", xaxis_title="Model")
st.plotly_chart(fig_bench, use_container_width=True)

st.header("2. Global Risk Drivers")

@st.cache_resource
def get_shap_global():
    sample_size = min(500, X_test.shape[0])
    X_sample = X_test[:sample_size]
    
    if hasattr(model, 'feature_importances_'):
        explainer = shap.TreeExplainer(model)
    elif hasattr(model, 'coef_'):
        explainer = shap.LinearExplainer(model, X_sample)
    else:
        explainer = shap.KernelExplainer(model.predict, X_sample)
        
    shap_values = explainer.shap_values(X_sample)
    
    if isinstance(shap_values, list):
        shap_values = shap_values[1]
        
    return shap_values, X_sample

shap_values_global, X_sample_global = get_shap_global()


FIXED_HEIGHT = 550

col_fi, col_shap = st.columns(2)

with col_fi:
    st.markdown("#### Feature Importance (XGBoost Weight)")
    fig_fi = px.bar(feature_importance_df, x='Importance', y='Feature', orientation='h', height=FIXED_HEIGHT)
    fig_fi.update_layout(margin=dict(l=0, r=0, t=30, b=0), height=FIXED_HEIGHT)
    st.plotly_chart(fig_fi, use_container_width=True)

with col_shap:
    st.markdown("#### Root Cause Analysis (SHAP)")
    st.markdown("<small><i>Impact direction across test data.</i></small>", unsafe_allow_html=True)
    
    
    shap.summary_plot(
        shap_values_global, 
        X_sample_global, 
        feature_names=selected_features, 
        max_display=20, 
        show=False, 
        plot_size=(8, 5.5) 
    )
    
    plt.tight_layout()
    st.pyplot(plt.gcf())
    plt.clf()

st.header("3. Risk Prediction Engine")

col_upload, col_settings = st.columns([2, 1])
with col_upload:
    uploaded_file = st.file_uploader("Upload New Orders (CSV)", type=['csv'], key="file_uploader")
with col_settings:
    threshold = st.slider("Risk Alert Threshold", min_value=0.1, max_value=0.9, value=0.5, step=0.05, 
                          help="Tăng ngưỡng này nếu model dự đoán 'Late' quá nhiều.")

col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    predict_btn = st.button("Analyze Risk", type="primary", width="stretch")

if 'df_result' not in st.session_state: st.session_state.df_result = None
if 'shap_data' not in st.session_state: st.session_state.shap_data = None

if uploaded_file is not None and predict_btn:
    try:
        df_upload = pd.read_csv(uploaded_file)
        
        missing_cols = set(all_features) - set(df_upload.columns)
        
        if missing_cols:
            st.error(f"Dữ liệu upload bị thiếu các cột gốc: {missing_cols}")
        else:
            X_upload_full_p = preprocessor.transform(df_upload)
            
            selected_indices = [all_features.index(feat) for feat in selected_features]
            X_upload_final = X_upload_full_p[:, selected_indices]
            
            pred_proba = model.predict_proba(X_upload_final)[:, 1]
            
            pred_label = (pred_proba >= threshold).astype(int)
            
            df_result = df_upload.copy()
            df_result['prob_late'] = pred_proba
            df_result['predicted_late'] = pred_label
            
            if 'actual_late' in df_result.columns:
                df_result['correct'] = (df_result['actual_late'] == df_result['predicted_late']).astype(int)
            
            st.session_state.df_result = df_result
            
            if hasattr(model, 'feature_importances_'):
                explainer_upload = shap.TreeExplainer(model)
            elif hasattr(model, 'coef_'):
                explainer_upload = shap.LinearExplainer(model, X_upload_final)
            else:
                explainer_upload = shap.KernelExplainer(model.predict, shap.sample(X_upload_final, 100))
                
            shap_values_upload = explainer_upload.shap_values(X_upload_final)
            
            if isinstance(shap_values_upload, list):
                shap_values_upload = shap_values_upload[1]
                expected_value = explainer_upload.expected_value[1]
            else:
                expected_value = explainer_upload.expected_value
                
            st.session_state.shap_data = {
                'values': shap_values_upload,
                'expected_value': expected_value,
                'X': X_upload_final
            }
            st.success("Prediction completed successfully!")
            
    except Exception as e:
        st.error(f"Error during prediction: {e}")

if st.session_state.df_result is not None:
    df_result = st.session_state.df_result
    shap_data = st.session_state.shap_data
    
    st.markdown("---")
    st.subheader("4. Prediction Results & Actions")
    
    total_orders = len(df_result)
    late_orders = df_result['predicted_late'].sum()
    on_time_orders = total_orders - late_orders
    late_rate = (late_orders / total_orders) * 100

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Total Orders Processed", total_orders)
    col_m2.metric(f"Predicted Late (>{threshold:.2f})", late_orders, delta=f"{late_rate:.1f}% Risk Rate", delta_color="inverse")
    col_m3.metric("On Time", on_time_orders)
    
    csv_export = df_result.to_csv(index=False).encode('utf-8')
    with col_m4:
        st.download_button(
            label="Download Full Results",
            data=csv_export,
            file_name='prediction_results.csv',
            mime='text/csv',
            width="stretch"
        )

    st.write("") 

    col_f1, col_f2 = st.columns([1, 2])
    with col_f1:
        show_late_only = st.checkbox("Only show Late orders", value=True) 

    df_display = df_result.sort_values(by='prob_late', ascending=False)
    
    if show_late_only:
        df_display = df_display[df_display['predicted_late'] == 1]

    st.markdown("<small><i>Showing top results sorted by Risk Probability. Root Cause Analysis (SHAP) available for Late orders.</i></small>", unsafe_allow_html=True)
    
    display_limit = min(50, len(df_display))
    
    if len(df_display) == 0:
        st.success("Great! No late orders found matching your filter.")
    else:
        for i in range(display_limit):
            real_idx = df_display.index[i] 
            row = df_display.iloc[i]
            
            is_late = row['predicted_late'] == 1
            prob = row['prob_late']
            
            if is_late:
                with st.expander(f"Order ID/Row: {real_idx} | Risk: LATE (Probability: {prob:.1%})", expanded=False):
                    st.dataframe(pd.DataFrame(row).T.style.set_properties(**{'background-color': '#ffe6e6', 'color': '#990000'}))
                    
                    col_shap_loc, col_recom = st.columns([1.5, 1])
                    with col_shap_loc:
                        st.caption("Why is it Late? (SHAP Analysis)")
                        plt.figure(figsize=(6, 3)) 
                        shap.waterfall_plot(shap.Explanation(
                            values=shap_data['values'][real_idx],
                            base_values=shap_data['expected_value'],
                            data=shap_data['X'][real_idx],
                            feature_names=selected_features
                        ), show=False, max_display=6) 
                        plt.tight_layout()
                        st.pyplot(plt.gcf())
                        plt.clf()
                        
                    with col_recom:
                        st.caption("Recommended Actions")
                        st.warning("**High Risk Detected**\n\n- Check supplier lead time.\n- Expedite shipping method.\n- Notify customer of potential delay.")
            else:
                with st.expander(f"Order ID/Row: {real_idx} | Risk: LOW (Probability: {prob:.1%})", expanded=False):
                    st.dataframe(pd.DataFrame(row).T.style.set_properties(**{'background-color': '#e6ffe6', 'color': '#006600'}))