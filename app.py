import os
import sys
import subprocess
import time

# ---------------------------------------------------------
# ★超強力版: サーバーのライブラリ強制入れ替え処理
# ---------------------------------------------------------
# 1. まず既存の古いライブラリを強制削除
try:
    subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", "google-generativeai"])
except:
    pass

# 2. 最新版 (0.8.3) をインストール
try:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-generativeai==0.8.3"])
except Exception as e:
    print(f"Install Error: {e}")

# 3. インストール後にインポート
import google.generativeai as genai

# ---------------------------------------------------------
# 通常のライブラリ
# ---------------------------------------------------------
import streamlit as st
import pandas as pd
from PIL import Image
import re
import json
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
# 1. 脳みそ (検索必須・ハルシネーション厳禁)
# ==========================================
KUSANO_BRAIN = """
あなたは、市立長浜病院・臨床工学技術科次長「草野（Kusano）」です。
提供された情報を統合し、論理的に診断推論を行ってください。

【Check!! 絶対ルール】
あなたはAIであり、嘘をつくリスクがあります。
**必ず「Google検索ツール」を使用して裏付けを取り、事実に基づいた回答のみを行ってください。**
もし検索機能がエラーで使えない場合は、決して推測で回答せず、正直に「システムエラーのため回答できません」と伝えてください。

【情報の格付け】
- 推奨: .go.jp, .ac.jp, .or.jp (公的機関・学会)
- 注意: 個人ブログ、まとめサイト (原則除外)

【回答フォーマット】
1. **Clinical Summary**: 状態要約
2. **Integrated Assessment**: 病歴×数値トレンドの統合見解
3. **Evidence**: 根拠とした文献と信頼度
4. **Plan**: 推奨アクション
"""

# ==========================================
# 2. データ管理 & サイドバー
# ==========================================
if 'patient_db' not in st.session_state:
    st.session_state['patient_db'] = {}

current_patient_id = None 

with st.sidebar:
    st.title("⚙️ System Config")
    
    # バージョン確認 (0.8.3になっているはず)
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
            
            # 保存・読込機能
            current_data = st.session_state['patient_db'].get(current_patient_id, [])
            if current_data:
                json_str = json.dumps(current_data, indent=2, default=str)
                st.download_button("📥 データ保存", json_str, file_name=f"{current_patient_id}.json", mime="application/json")
            
            uploaded_file = st.file_uploader("📤 データ読込", type=["json"])
            if uploaded_file:
                try:
                    st.session_state['patient_db'][current_patient_id] = json.load(uploaded_file)
                    st.success("復元完了")
                except: pass

            st.markdown("---")
            if st.button("🗑️ 履歴消去"):
                st.session_state['patient_db'][current_patient_id] = []
                st.rerun()

# ==========================================
# 3. メイン画面
# ==========================================
st.title(f"👨‍⚕️ {APP_TITLE}")

if not current_patient_id:
    st.stop()

st.caption(f"Patient ID: **{current_patient_id}**")
tab1, tab2 = st.tabs(["📝 総合診断 (Strict Search)", "📈 トレンド管理"])

# === TAB 2: トレンド管理 (グラフ修正済) ===
with tab2:
    st.info("数値入力")
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

    if st.button("💾 記録"):
        if current_patient_id not in st.session_state['patient_db']: st.session_state['patient_db'][current_patient_id] = []
        st.session_state['patient_db'][current_patient_id].append({"Time": datetime.now().strftime("%H:%M:%S"), "P/F": pf, "DO2": do2, "O2ER": o2er, "Lactate": lac, "Hb": hb})
        st.rerun()
    
    hist = st.session_state['patient_db'].get(current_patient_id, [])
    if hist:
        df = pd.DataFrame(hist)
        # グラフ用データ整形（数値化）
        for col in ["P/F", "DO2", "O2ER", "Lactate", "Hb"]:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
        
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("##### 呼吸・代謝")
            st.line_chart(df.set_index("Time")[["P/F", "O2ER", "Lactate"]])
        with g2:
            st.markdown("##### 循環")
            st.line_chart(df.set_index("Time")[["DO2", "Hb"]])

# === TAB 1: 診断 (検索エラー完全対応版) ===
with tab1:
    col1, col2 = st.columns(2)
    hist_text = col1.text_area("病歴")
    lab_text = col1.text_area("検査データ")
    up_file = col2.file_uploader("画像", accept_multiple_files=True)

    if st.button("🔍 診断実行 (検索必須)"):
        if not api_key:
            st.error("APIキーを入れてください！")
        else:
            trend_str = "なし"
            hist = st.session_state['patient_db'].get(current_patient_id, [])
            if hist: trend_str = pd.DataFrame(hist).tail(5).to_markdown(index=False)
            
            content = [f"病歴: {hist_text}\nデータ: {lab_text}\nトレンド: {trend_str}"]
            if up_file:
                for f in up_file: content.append(Image.open(f))

            # ★検索実行ロジック (ダブルチェック)
            try:
                model = genai.GenerativeModel("gemini-1.5-pro", system_instruction=KUSANO_BRAIN)
                
                with st.spinner("思考中... (Google検索を実行中)"):
                    # まず標準的な書き方でトライ
                    try:
                        res = model.generate_content(content, tools=[{'google_search': {}}])
                    except Exception as inner_e:
                        # 失敗したら、古いバージョン向けの書き方で再トライ（Unknown field対策）
                        if "Unknown field" in str(inner_e):
                            # 古いプロトコル向けの空ツール定義などで誤魔化すのではなく
                            # そもそもバージョンが古いなら強制停止させるべきだが
                            # 今回は冒頭で強制アップデートしているので、ここに来るはずがない。
                            # 念の為、別の書き方を試す
                            res = model.generate_content(content, tools=[{'google_search_retrieval': {}}])
                        else:
                            raise inner_e # その他のエラーは投げる

                st.markdown("### 👨‍⚕️ Assessment Result")
                st.write(res.text)
                
                # 参照元表示
                if res.candidates[0].grounding_metadata.search_entry_point:
                    st.success("✅ 参照文献あり")
                    st.write(res.candidates[0].grounding_metadata.search_entry_point.rendered_content)
                else:
                    st.warning("⚠️ 検索結果が得られませんでした。")

            except Exception as e:
                st.error("❌ 検索機能エラー")
                st.error(f"詳細: {e}")
                st.error("ハルシネーション防止のため、処理を中断しました。")
