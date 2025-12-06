import os
import sys
import subprocess
import json

# ---------------------------------------------------------
# ★サーバーのライブラリを強制的に最新版にする
# ---------------------------------------------------------
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
あなたはAIであり、ハルシネーション（事実に基づかない回答）を起こすリスクがあります。
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
            
            # --- ここを修正：ボタンの挙動を分かりやすく ---
            st.markdown("### 💾 データバックアップ")
            
            current_data = st.session_state['patient_db'].get(current_patient_id, [])
            
            if current_data:
                # データがある場合：ダウンロードボタンを表示
                # ensure_ascii=False で日本語文字化けを防止
                json_str = json.dumps(current_data, indent=2, default=str, ensure_ascii=False)
                st.download_button(
                    label="📥 データを保存 (Download)",
                    data=json_str,
                    file_name=f"{current_patient_id}.json",
                    mime="application/json",
                    key="dl_btn_active"
                )
            else:
                # データがない場合：理由を表示してグレーアウト
                st.info("※「📈 トレンド管理」タブで数値を入力し、「💾 記録」ボタンを押すと、ここに保存ボタンが現れます。")
                st.button("📥 データなし (保存不可)", disabled=True, key="dl_btn_disabled")
            
            uploaded_file = st.file_uploader("📤 データを復元 (Upload)", type=["json"])
            if uploaded_file:
                try:
                    loaded_data = json.load(uploaded_file)
                    st.session_state['patient_db'][current_patient_id] = loaded_data
                    st.success(f"復元完了！ ({len(loaded_data)}件)")
                    # 画面更新ボタン
                    if st.button("🔄 グラフを更新"):
                        st.rerun()
                except:
                    st.error("ファイルが壊れています")

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

# === TAB 2: トレンド管理 ===
with tab2:
    st.info("数値を入力して「記録」を押してください")
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

    # 記録ボタン (ここを押さないと保存ボタンは出ません！)
    if st.button("💾 記録 (Memory)"):
        if current_patient_id not in st.session_state['patient_db']: st.session_state['patient_db'][current_patient_id] = []
        st.session_state['patient_db'][current_patient_id].append({"Time": datetime.now().strftime("%H:%M:%S"), "P/F": pf, "DO2": do2, "O2ER": o2er, "Lactate": lac, "Hb": hb})
        st.rerun()
    
    hist = st.session_state['patient_db'].get(current_patient_id, [])
    if hist:
        df = pd.DataFrame(hist)
        for col in ["P/F", "DO2", "O2ER", "Lactate", "Hb"]:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
        
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("##### 呼吸・代謝")
            st.line_chart(df.set_index("Time")[["P/F", "O2ER", "Lactate"]])
        with g2:
            st.markdown("##### 循環")
            st.line_chart(df.set_index("Time")[["DO2", "Hb"]])

# === TAB 1: 診断 (厳格モード) ===
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

            try:
                # 1. モデル作成
                model = genai.GenerativeModel("gemini-1.5-pro", system_instruction=KUSANO_BRAIN)
                
                with st.spinner("思考中... (Google検索で裏付け確認中)"):
                    # 2. 実行時にツールを渡す
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
                    st.warning("⚠️ 検索を行いましたが、関連する文献が見つかりませんでした。")

            except Exception as e:
                st.error("❌ 検索機能エラー")
                st.error(f"詳細: {e}")
                st.error("ハルシネーション防止のため、診断を中止します。")
