import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
from duckduckgo_search import DDGS
from datetime import datetime
import json

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
# 1. 脳みそ (自力検索・RAG型)
# ==========================================
KUSANO_BRAIN = """
あなたは、市立長浜病院・臨床工学技術科次長「草野（Kusano）」です。
提供された「患者データ」と「検索された最新情報」を統合し、論理的に診断推論を行ってください。

【絶対ルール：情報の信頼性評価】
提供された【検索結果】の中から、信頼できる情報源（学会、公的機関、論文）を優先して根拠としてください。
検索結果に含まれる内容のみを事実として扱い、あなたの記憶だけで不確実な情報を補完（ハルシネーション）することは厳禁です。

【回答フォーマット】
1. **Clinical Summary**: 患者の状態要約
2. **Integrated Assessment**: 病歴×数値トレンド×検索結果の統合見解
3. **Evidence**: 根拠とした文献（検索結果のSource）と信頼度
4. **Plan**: 推奨アクション
"""

# ==========================================
# 2. データ管理
# ==========================================
if 'patient_db' not in st.session_state:
    st.session_state['patient_db'] = {}

current_patient_id = None 

# ==========================================
# 3. サイドバー
# ==========================================
with st.sidebar:
    st.title("⚙️ System Config")
    st.caption("Mode: External Search (DDG)")

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
            
            # データ保存・読込
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
# 4. メイン画面
# ==========================================
st.title(f"👨‍⚕️ {APP_TITLE}")

if not current_patient_id:
    st.stop()

st.caption(f"Patient ID: **{current_patient_id}**")
tab1, tab2 = st.tabs(["📝 総合診断 (With Search)", "📈 トレンド管理"])

# ------------------------------------------------
# TAB 2: トレンド管理
# ------------------------------------------------
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
# TAB 1: 総合診断 (DuckDuckGo実装版)
# ------------------------------------------------
with tab1:
    col1, col2 = st.columns(2)
    hist_text = col1.text_area("病歴")
    lab_text = col1.text_area("検査データ")
    up_file = col2.file_uploader("画像", accept_multiple_files=True)

    if st.button("🔍 診断実行 (検索付)"):
        if not api_key:
            st.error("APIキーを入れてください！")
        else:
            trend_str = "なし"
            hist = st.session_state['patient_db'].get(current_patient_id, [])
            if hist: trend_str = pd.DataFrame(hist).tail(5).to_markdown(index=False)
            
            # --- 1. Pythonで検索を実行 (エラー知らず) ---
            search_context = ""
            try:
                with st.spinner("最新情報を検索中... (Powered by DuckDuckGo)"):
                    # 検索ワードを作成
                    query = f"医療ガイドライン {hist_text[:40]} 診断 治療"
                    with DDGS() as ddgs:
                        # 日本語の結果を3件取得
                        results = list(ddgs.text(query, region='jp-jp', max_results=3))
                        for i, r in enumerate(results):
                            search_context += f"【検索結果{i+1}】\nTitle: {r['title']}\nURL: {r['href']}\nContent: {r['body']}\n\n"
            except Exception as e:
                search_context = f"（検索エラー: {e}）"

            # --- 2. AIに情報を渡す ---
            prompt_text = f"""
            以下の情報を【統合的に】分析してください。

            【Tab 1: 病歴】{hist_text}
            【Tab 1: 検査】{lab_text}
            【Tab 2: トレンド(直近5点)】{trend_str}

            【検索された最新情報 (Search Results)】
            {search_context}
            """
            
            content = [prompt_text]
            if up_file:
                for f in up_file: content.append(Image.open(f))

            try:
                # toolsは使わない (これがエラー回避の絶対条件)
                model = genai.GenerativeModel("gemini-1.5-pro", system_instruction=KUSANO_BRAIN)
                
                with st.spinner("思考中... (検索結果を統合解析)"):
                    res = model.generate_content(content)
                
                st.markdown("### 👨‍⚕️ Assessment Result")
                st.write(res.text)
                
                if search_context and "検索エラー" not in search_context:
                    with st.expander("🔍 参照した検索結果ソース"):
                        st.text(search_context)

            except Exception as e:
                st.error(f"エラー発生: {e}")
