import os
import sys
import subprocess
import json

# ---------------------------------------------------------
# ★サーバー環境の強制最適化 (エラー回避の守護神)
# ---------------------------------------------------------
try:
    import google.generativeai
    # 古いライブラリなら強制アップデート
    if getattr(google.generativeai, "__version__", "0.0.0") < "0.8.3":
        subprocess.check_call([sys.executable, "-m", "pip", "install", "google-generativeai==0.8.3"])
        import google.generativeai as genai
    else:
        import google.generativeai as genai
except:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-generativeai==0.8.3"])
    import google.generativeai as genai

import streamlit as st
import pandas as pd
from PIL import Image
import re
from datetime import datetime
from duckduckgo_search import DDGS # 外部検索エンジン

# ==========================================
# 0. アプリ設定
# ==========================================
COMPANY_NAME = "K's tech works. (K&G solution)"
APP_TITLE = "Super Clinical Decision Support"

st.set_page_config(page_title=APP_TITLE, layout="wide", page_icon="👨‍⚕️")

st.markdown(f"""
    <style>
    .footer {{
        position: fixed; left: 0; bottom: 0; width: 100%;
        background-color: #0E1117; color: #FAFAFA;
        text-align: center; padding: 10px; font-weight: bold;
        border-top: 1px solid #444; z-index: 100; font-family: sans-serif;
    }}
    .block-container {{ padding-bottom: 80px; }}
    /* スマホで見やすいように調整 */
    p, li {{ font-size: 16px !important; }}
    .stAlert {{ font-weight: bold; }}
    </style>
    <div class="footer">Produced by {COMPANY_NAME}</div>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 脳みそ (医師同等・厳格仕様)
# ==========================================
KUSANO_BRAIN = """
あなたは、市立長浜病院・臨床工学技術科次長「草野（Kusano）」です。
「事実」と「推論」を区別し、特に**「アクションの優先順位」**を明確にして回答してください。

【絶対ルール】
緊急性の高い現場（スマホ閲覧）を想定し、結論ファーストで簡潔に記述すること。
検索結果（Search Results）の内容を重視し、ハルシネーション（嘘）を防ぐこと。

【回答セクション構成】（以下のタグを必ず守ること）

---SECTION_PLAN_EMERGENCY---
**【最優先・緊急アクション (Do Now)】**
生命維持のために「今すぐ」行うべき処置・オーダーのみを箇条書きで。
（例：昇圧剤開始、挿管準備、急速輸液など）

---SECTION_AI_OPINION---
**【病態推論・クロスオーバー分析】**
病歴とトレンドデータの矛盾（DO2とLactateの乖離など）や、隠れた病態（Warm Shock, DKA等）への言及。

---SECTION_PLAN_ROUTINE---
**【次の一手・管理方針 (Do Next)】**
緊急処置の次に行うべき検査、モニタリング項目、根本治療計画。

---SECTION_FACT---
**【エビデンス・根拠】**
検索結果に基づくガイドラインや文献の引用。
"""

# ==========================================
# 2. データ管理
# ==========================================
if 'patient_db' not in st.session_state:
    st.session_state['patient_db'] = {}

current_patient_id = None 
selected_model_name = None

# ==========================================
# 3. サイドバー
# ==========================================
with st.sidebar:
    st.title("⚙️ System Config")
    st.caption("Mode: Medical Safety First")

    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("🔑 API Key Loaded")
    except:
        api_key = st.text_input("Gemini API Key", type="password")
    
    if api_key:
        genai.configure(api_key=api_key)
        try:
            model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            default_index = 0
            for i, m_name in enumerate(model_list):
                if "gemini-1.5-pro" in m_name:
                    default_index = i
                    break
            selected_model_name = st.selectbox("使用モデル", model_list, index=default_index)
        except: st.error("Model Error")

    st.markdown("---")
    patient_id_input = st.text_input("🆔 患者ID (半角英数)", value="TEST1", max_chars=10)
    
    if patient_id_input:
        if not re.match(r'^[a-zA-Z0-9]+$', patient_id_input):
            st.error("⚠️ 英数字のみ")
        else:
            current_patient_id = patient_id_input.upper()
            st.success(f"Login: {current_patient_id}")
            
            # --- 保存・読込 ---
            st.markdown("### 💾 データ管理")
            current_data = st.session_state['patient_db'].get(current_patient_id, [])
            
            if current_data:
                json_str = json.dumps(current_data, indent=2, default=str, ensure_ascii=False)
                st.download_button("📥 データを保存", json_str, f"{current_patient_id}.json", "application/json", key="dl_btn")
            else:
                st.info("※記録すると保存ボタンが出現")
                st.button("📥 データなし", disabled=True, key="dl_btn_d")
            
            uploaded_file = st.file_uploader("📤 データを復元", type=["json"], key="up_btn")
            if uploaded_file:
                try:
                    loaded_data = json.load(uploaded_file)
                    st.session_state['patient_db'][current_patient_id] = loaded_data
                    st.success(f"復元成功 ({len(loaded_data)}件)")
                    if st.button("🔄 グラフ反映"): st.rerun()
                except: pass
            
            st.markdown("---")
            if st.button("🗑️ 履歴消去", key="del_btn"):
                st.session_state['patient_db'][current_patient_id] = []
                st.rerun()

# ==========================================
# 4. メイン画面
# ==========================================
st.title(f"👨‍⚕️ {APP_TITLE}")

if not current_patient_id:
    st.stop()

st.caption(f"Patient: **{current_patient_id}**")
tab1, tab2 = st.tabs(["📝 総合診断 (Smart Search)", "📈 トレンド管理"])

# === TAB 2: トレンド管理 (AG・電解質・グラフ修正完備) ===
with tab2:
    st.info("数値入力 (必要な項目のみ)")
    
    # 呼吸・循環・代謝
    st.caption("▼ 呼吸・循環・代謝")
    c1, c2, c3 = st.columns(3)
    pao2 = c1.number_input("PaO2", step=1.0, value=None, key="n_pao2")
    fio2 = c1.number_input("FiO2", step=1.0, value=None, key="n_fio2")
    lac = c1.number_input("Lactate", step=0.1, value=None, key="n_lac")
    
    hb = c2.number_input("Hb", step=0.1, value=None, key="n_hb")
    co = c2.number_input("CO", step=0.1, value=None, key="n_co")
    spo2 = c2.number_input("SpO2", step=1.0, value=None, key="n_spo2")
    
    ph = c3.number_input("pH", step=0.01, value=None, key="n_ph")
    svo2 = c3.number_input("SvO2", step=1.0, value=None, key="n_svo2")

    # 電解質・AG (DKA診断用)
    st.caption("▼ 電解質 (AG計算用)")
    e1, e2, e3, e4 = st.columns(4)
    na = e1.number_input("Na", step=1.0, value=None, key="n_na")
    cl = e2.number_input("Cl", step=1.0, value=None, key="n_cl")
    hco3 = e3.number_input("HCO3", step=0.1, value=None, key="n_hco3")
    alb = e4.number_input("Alb", step=0.1, value=None, key="n_alb")

    # --- 計算ロジック ---
    pf, do2, o2er, ag, c_ag = None, None, None, None, None
    
    if pao2 and fio2 and fio2>0: pf = pao2 / (fio2/100)
    if hb and co and spo2 and pao2:
        cao2 = 1.34*hb*(spo2/100) + 0.0031*pao2
        do2 = co*cao2*10
        if svo2:
            cvo2 = 1.34*hb*(svo2/100) + 0.0031*40
            vo2 = co*(cao2-cvo2)*10
            if do2 and do2>0: o2er = (vo2/do2)*100
    
    if na and cl and hco3:
        ag = na - (cl + hco3)
        if alb: c_ag = ag + 2.5 * (4.0 - alb) # 補正AG

    # プレビュー
    cols = st.columns(4)
    if pf: cols[0].metric("P/F", f"{pf:.0f}")
    if do2: cols[1].metric("DO2", f"{do2:.0f}")
    if o2er: cols[2].metric("O2ER", f"{o2er:.1f}%")
    if c_ag: cols[3].metric("AG(補正)", f"{c_ag:.1f}")
    elif ag: cols[3].metric("AG(実測)", f"{ag:.1f}")

    if st.button("💾 記録"):
        if current_patient_id not in st.session_state['patient_db']: st.session_state['patient_db'][current_patient_id] = []
        
        record = {
            "Time": datetime.now().strftime("%H:%M:%S"),
            "P/F": pf, "DO2": do2, "O2ER": o2er, 
            "Lactate": lac, "Hb": hb, "pH": ph,
            "AG": c_ag if c_ag else ag # AGも保存
        }
        st.session_state['patient_db'][current_patient_id].append(record)
        st.rerun()
    
    # --- グラフ描画 (エラー絶対回避版) ---
    hist = st.session_state['patient_db'].get(current_patient_id, [])
    if hist:
        df = pd.DataFrame(hist)
        
        # 必須カラムがなくても落ちないように補完
        target_cols = ["P/F", "DO2", "O2ER", "Lactate", "Hb", "pH", "AG"]
        for col in target_cols:
            if col not in df.columns: df[col] = None
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("##### 呼吸・代謝 (P/F, O2ER, Lac)")
            # データがある列だけプロット
            available_cols1 = [c for c in ["P/F", "O2ER", "Lactate"] if df[c].notna().any()]
            if available_cols1: st.line_chart(df.set_index("Time")[available_cols1])
            
        with g2:
            st.markdown("##### 酸塩基・循環 (AG, pH, DO2)")
            available_cols2 = [c for c in ["AG", "pH", "DO2"] if df[c].notna().any()]
            if available_cols2: st.line_chart(df.set_index("Time")[available_cols2])
        
        with st.expander("🔍 生データ確認"): st.dataframe(df)

# === TAB 1: 総合診断 (スマホ最適化UI + スマート検索) ===
with tab1:
    col1, col2 = st.columns(2)
    hist_text = col1.text_area("病歴")
    lab_text = col1.text_area("検査データ")
    up_file = col2.file_uploader("画像", accept_multiple_files=True)

    if st.button("🔍 診断実行"):
        if not api_key:
            st.error("APIキーを入れてください")
        else:
            trend_str = "なし"
            hist = st.session_state['patient_db'].get(current_patient_id,
