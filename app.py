import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
import re
import json
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
    button[data-baseweb="tab"] {{ font-size: 18px !important; font-weight: bold !important; }}
    </style>
    <div class="footer">Produced by {COMPANY_NAME}</div>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 脳みそ (対等なパートナー・事実重視)
# ==========================================
KUSANO_BRAIN = """
あなたは、市立長浜病院・臨床工学技術科次長「草野（Kusano）」です。
医療チームの一員として、提供された情報を統合し、論理的かつ客観的な診断推論を行ってください。

【絶対ルール】
1. **相手を選ばないプロの口調**:
   - 相手がベテラン医師か若手かに関わらず、**「敬意を持った対等な臨床パートナー」**として振る舞ってください。「若手医師よ」といった上からの呼びかけは禁止です。
   - 結論を先に述べ、その後に根拠を示す「結論ファースト」を徹底してください。

2. **事実の厳守 (No Hallucination)**:
   - 提供されたデータにない数値（架空のトレンドデータなど）を勝手に創作してストーリーを作らないでください。
   - 検索機能を使用する際は、必ず情報の出所（ドメイン）を確認し、信頼できるソースのみを根拠としてください。

【情報の格付け】
- 推奨: .go.jp, .ac.jp, .or.jp (公的機関・学会)
- 注意: 個人ブログ、まとめサイト (原則除外)

【回答フォーマット】
1. **Clinical Summary**: 患者の状態要約
2. **Integrated Assessment**: 病歴×数値トレンドの統合見解
   - ※データの矛盾（例: SpO2とP/Fの乖離）があれば鋭く指摘すること。
3. **Evidence**: 根拠とした文献と信頼度
4. **Plan**: 推奨アクション（具体的数値を含むこと）
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
    st.caption("Mode: Medical Advice (DDG)")

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
            selected_model_name = st.selectbox("使用モデルを選択", model_list, index=default_index)
        except Exception as e:
            st.error(f"モデルリスト取得失敗: {e}")

    st.markdown("---")
    patient_id_input = st.text_input("🆔 患者ID (半角英数)", value="TEST1", max_chars=10)
    
    if patient_id_input:
        if not re.match(r'^[a-zA-Z0-9]+$', patient_id_input):
            st.error("⚠️ 半角英数字のみ")
        else:
            current_patient_id = patient_id_input.upper()
            st.success(f"Login: {current_patient_id}")
            
            # --- 保存・読込 ---
            current_data = st.session_state['patient_db'].get(current_patient_id, [])
            if current_data:
                json_str = json.dumps(current_data, indent=2, default=str, ensure_ascii=False)
                st.download_button("📥 データを保存", json_str, file_name=f"{current_patient_id}.json", mime="application/json", key="dl_btn")
            else:
                st.button("📥 データなし", disabled=True, key="dl_btn_d")
            
            uploaded_file = st.file_uploader("📤 データを復元", type=["json"], key="up_btn")
            if uploaded_file:
                try:
                    loaded_data = json.load(uploaded_file)
                    st.session_state['patient_db'][current_patient_id] = loaded_data
                    st.success("復元完了")
                    if st.button("🔄 反映"): st.rerun()
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

st.caption(f"Patient ID: **{current_patient_id}** | Model: **{selected_model_name}**")
tab1, tab2 = st.tabs(["📝 総合診断 (Medical Advice)", "📈 トレンド管理"])

# === TAB 2: トレンド管理 ===
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
        
        with st.expander("🔍 生データ確認"):
            st.dataframe(df)

# === TAB 1: 総合診断 (スマート検索 & ガチアドバイス) ===
with tab1:
    col1, col2 = st.columns(2)
    hist_text = col1.text_area("病歴")
    lab_text = col1.text_area("検査データ")
    up_file = col2.file_uploader("画像", accept_multiple_files=True)

    if st.button("🔍 診断実行 (検索付)"):
        if not api_key:
            st.error("APIキーを入れてください！")
        elif not selected_model_name:
            st.error("モデルが選択されていません。サイドバーを確認してください。")
        else:
            trend_str = "なし"
            hist = st.session_state['patient_db'].get(current_patient_id, [])
            if hist: trend_str = pd.DataFrame(hist).tail(5).to_markdown(index=False)
            
            # --- 1. Pythonで検索を実行 ---
            search_context = ""
            search_keywords = ""
            
            try:
                # まずキーワード生成
                model_kw = genai.GenerativeModel(model_name=selected_model_name)
                kw_prompt = f"以下の情報から、医学的診断に必要な検索キーワードを3つ、スペース区切りで作成せよ。記号は含めるな。\n{hist_text[:100]}\n{lab_text[:100]}"
                kw_res = model_kw.generate_content(kw_prompt)
                search_keywords = kw_res.text.strip()

                with st.spinner(f"最新情報を検索中... ({search_keywords})"):
                    # 検索実行
                    with DDGS() as ddgs:
                        results = list(ddgs.text(f"{search_keywords} ガイドライン", region='jp-jp', max_results=3))
                        for i, r in enumerate(results):
                            search_context += f"【検索結果{i+1}】\nTitle: {r['title']}\nURL: {r['href']}\nContent: {r['body']}\n\n"
            except Exception as e:
                search_context = f"（検索エラー: {e}）"

            # --- 2. AIへプロンプト ---
            prompt_text = f"""
            以下の情報を【統合的に】分析してください。
            【Tab 1: 病歴】{hist_text}
            【Tab 1: 検査】{lab_text}
            【Tab 2: トレンド(直近5点)】{trend_str}
            【検索された最新情報】{search_context}
            """
            
            content = [prompt_text]
            if up_file:
                for f in up_file: content.append(Image.open(f))

            try:
                # 3. 診断生成
                model = genai.GenerativeModel(model_name=selected_model_name, system_instruction=KUSANO_BRAIN)
                
                with st.spinner("思考中... (検索結果を統合解析)"):
                    res = model.generate_content(content)
                
                st.markdown("### 👨‍⚕️ Assessment Result")
                st.write(res.text)
                
                if search_context and "検索エラー" not in search_context:
                    with st.expander(f"🔍 参照した検索結果 ({search_keywords})"):
                        st.text(search_context)

            except Exception as e:
                st.error(f"エラー発生: {e}")
