import os
import sys
import subprocess
import json # 保存用にjsonを使う

# --- 強制アップデート ---
try:
    import google.generativeai
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
    button[data-baseweb="tab"] {{ font-size: 18px !important; font-weight: bold !important; }}
    </style>
    <div class="footer">Produced by {COMPANY_NAME}</div>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 脳みそ
# ==========================================
KUSANO_BRAIN = """
あなたは、市立長浜病院・臨床工学技術科次長「草野（Kusano）」です。
提供された情報を統合し、論理的に診断推論を行ってください。

【絶対ルール】
Google検索機能を使用する際は、必ず情報の出所（ドメイン）を確認し、以下の基準で情報の信頼性を評価してください。

1. **推奨ソース**: .go.jp, .ac.jp, .or.jp, pubmed, jstage など
2. **非推奨**: 個人ブログ、まとめサイト

【回答フォーマット】
1. **Clinical Summary**: 患者の状態要約。
2. **Integrated Assessment**: 病歴と数値を統合した見解。
3. **Evidence & Grading**: 参照文献と信頼度（高/低）。
4. **Plan / Action**: 推奨アクション。
"""

# ==========================================
# 2. データ管理
# ==========================================
if 'patient_db' not in st.session_state:
    st.session_state['patient_db'] = {}

current_patient_id = None 

# ==========================================
# 3. サイドバー (保存・読込機能追加！)
# ==========================================
with st.sidebar:
    st.title("⚙️ System Config")
    st.caption(f"GenAI Lib: {genai.__version__}")

    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("🔑 API Key Loaded")
    except:
        api_key = st.text_input("Gemini API Key", type="password")
    
    if api_key:
        genai.configure(api_key=api_key)

    st.markdown("---")
    patient_id_input = st.text_input("🆔 患者ID (半角英数)", value="TEST1", max_chars=10)
    
    if patient_id_input:
        if not re.match(r'^[a-zA-Z0-9]+$', patient_id_input):
            st.error("⚠️ 半角英数字のみ")
        else:
            current_patient_id = patient_id_input.upper()
            st.success(f"Login: {current_patient_id}")
            
            # --- データの保存・読込 ---
            st.markdown("### 💾 データ管理")
            
            # 保存ボタン
            # 現在のIDのデータをJSON文字列に変換してダウンロードさせる
            current_data = st.session_state['patient_db'].get(current_patient_id, [])
            if current_data:
                json_str = json.dumps(current_data, indent=2, default=str)
                st.download_button(
                    label="📥 データを保存 (Download)",
                    data=json_str,
                    file_name=f"{current_patient_id}_data.json",
                    mime="application/json"
                )
            
            # 読込ボタン
            uploaded_file = st.file_uploader("📤 データを読込 (Upload)", type=["json"])
            if uploaded_file is not None:
                try:
                    loaded_data = json.load(uploaded_file)
                    # データを上書き結合
                    st.session_state['patient_db'][current_patient_id] = loaded_data
                    st.success("復元しました！")
                except:
                    st.error("ファイルが壊れています")

            st.markdown("---")
            if st.button("🗑️ 履歴全消去"):
                st.session_state['patient_db'][current_patient_id] = []
                st.rerun()

# ==========================================
# 4. メイン画面
# ==========================================
st.title(f"👨‍⚕️ {APP_TITLE}")

if not current_patient_id:
    st.stop()

st.caption(f"Patient ID: **{current_patient_id}**")

tab1, tab2 = st.tabs(["📝 総合診断 (Crossover)", "📈 トレンド管理"])

# ------------------------------------------------
# TAB 2: トレンド管理
# ------------------------------------------------
with tab2:
    st.info("数値入力 (必要な項目のみ)")
    c1, c2, c3 = st.columns(3)
    pao2 = c1.number_input("PaO2", step=1.0, value=None, key="n_pao2")
    fio2 = c1.number_input("FiO2", step=1.0, value=None, key="n_fio2")
    lac = c1.number_input("Lactate", step=0.1, value=None, key="n_lac")
    hb = c2.number_input("Hb", step=0.1, value=None, key="n_hb")
    co = c2.number_input("CO", step=0.1, value=None, key="n_co")
    spo2 = c2.number_input("SpO2", step=1.0, value=None, key="n_spo2")
    ph = c3.number_input("pH", step=0.01, value=None, key="n_ph")
    svo2 = c3.number_input("SvO2", step=1.0, value=None, key="n_svo2")

    pf, do2, o2er = None, None, None
    if pao2 and fio2 and fio2>0: pf = pao2 / (fio2/100)
    if hb and co and spo2 and pao2:
        cao2 = 1.34*hb*(spo2/100) + 0.0031*pao2
        do2 = co*cao2*10
        if svo2:
            cvo2 = 1.34*hb*(svo2/100) + 0.0031*40
            vo2 = co*(cao2-cvo2)*10
            if do2 and do2>0: o2er = (vo2/do2)*100
    
    cols = st.columns(3)
    if pf: cols[0].metric("P/F", f"{pf:.0f}")
    if do2: cols[1].metric("DO2", f"{do2:.0f}")
    if o2er: cols[2].metric("O2ER", f"{o2er:.1f}%")

    if st.button("💾 記録 (Memory)"):
        if current_patient_id not in st.session_state['patient_db']: st.session_state['patient_db'][current_patient_id] = []
        st.session_state['patient_db'][current_patient_id].append({
            "Time": datetime.now().strftime("%H:%M:%S"), 
            "P/F": pf, "DO2": do2, "O2ER": o2er, "Lactate": lac, "Hb": hb
        })
        st.rerun()
    
    hist = st.session_state['patient_db'].get(current_patient_id, [])
    if hist:
        df = pd.DataFrame(hist)
        # 数値変換
        for col in ["P/F", "DO2", "O2ER", "Lactate", "Hb"]:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
        
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("##### 呼吸・代謝")
            st.line_chart(df.set_index("Time")[["P/F", "O2ER", "Lactate"]])
        with g2:
            st.markdown("##### 循環")
            st.line_chart(df.set_index("Time")[["DO2", "Hb"]])

# ------------------------------------------------
# TAB 1: 総合診断
# ------------------------------------------------
with tab1:
    col1, col2 = st.columns(2)
    hist_text = col1.text_area("病歴")
    lab_text = col1.text_area("検査データ")
    up_file = col2.file_uploader("画像", accept_multiple_files=True)

    if st.button("🔍 診断実行 (検索付き)"):
        if not api_key:
            st.error("APIキーを入れてください！")
        else:
            trend_str = "（トレンドデータなし）"
            hist = st.session_state['patient_db'].get(current_patient_id, [])
            if hist: trend_str = pd.DataFrame(hist).tail(5).to_markdown(index=False)
            
            prompt_text = f"""
            以下の情報を【統合的に】分析してください。
            Tab2のトレンド変化が、既往歴で説明できるか、新規病態かを鑑別してください。
            【Tab 1: 病歴】{hist_text}
            【Tab 1: 検査】{lab_text}
            【Tab 2: トレンド(直近5点)】{trend_str}
            """
            content = [prompt_text]
            if up_file:
                for f in up_file: content.append(Image.open(f))

            try:
                model = genai.GenerativeModel("gemini-1.5-pro", system_instruction=KUSANO_BRAIN)
                with st.spinner("思考中... (Google検索で裏付けを確認中)"):
                    res = model.generate_content(
                        content,
                        tools=[{"google_search": {}}]
                    )
                st.markdown("### 👨‍⚕️ Assessment Result")
                st.write(res.text)
                
                if res.candidates[0].grounding_metadata.search_entry_point:
                    st.success("✅ 文献・ガイドラインを参照しました")
                    st.write(res.candidates[0].grounding_metadata.search_entry_point.rendered_content)
                else:
                    st.info("※今回は内部知識のみで回答しました")

            except Exception as e:
                st.error(f"エラー発生: {e}")
