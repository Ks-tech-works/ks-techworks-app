import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
import re
import json
from datetime import datetime
from duckduckgo_search import DDGS

# ==========================================
# 0. アプリ設定 & MERA仕様デザイン (Dark Medical Cockpit Final V2.6)
# ==========================================
COMPANY_NAME = "K's tech works. (K&G solution)"
APP_TITLE = "Super Clinical Decision Support [PRO]"

st.set_page_config(page_title=APP_TITLE, layout="wide", page_icon="🫀")

# --- CSS: 医療用モニター風のUI/UX（視認性・コントラスト完全修正版） ---
st.markdown(f"""
    <style>
    /* 全体背景：漆黒 */
    .stApp {{ background-color: #000000; color: #FFFFFF; }}
    
    /* 基本テキスト */
    h1, h2, h3, h4, h5, h6, p, li, span, div {{ color: #E0E0E0 !important; }}
    label, .stTextInput label, .stNumberInput label, .stTextArea label {{ color: #FFFFFF !important; font-weight: bold !important; }}
    
    /* サイドバー */
    [data-testid="stSidebar"] {{ background-color: #111111; border-right: 1px solid #333; }}
    [data-testid="stSidebar"] * {{ color: #CCCCCC !important; }}

    /* メトリックカード（数値表示部） */
    div[data-testid="metric-container"] {{
        background-color: #1E1E1E; border: 1px solid #444;
        padding: 10px; border-radius: 5px;
        box-shadow: 0 0 10px rgba(0, 255, 255, 0.1);
    }}
    div[data-testid="metric-container"] label {{ color: #AAAAAA !important; }}
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {{ color: #00FFFF !important; }}
    
    /* 入力ボックス & セレクトボックスの強制ダークモード化 */
    .stNumberInput input, .stTextInput input, .stTextArea textarea {{
        background-color: #222222 !important; color: #FFFFFF !important; border: 1px solid #555 !important;
    }}
    
    /* Multiselect (選択ボックス) の視認性修正 */
    div[data-baseweb="select"] > div {{
        background-color: #222222 !important;
        color: #FFFFFF !important;
        border-color: #555 !important;
    }}
    /* 選択されたタグ (Chips) */
    div[data-baseweb="tag"] {{
        background-color: #333333 !important;
        border: 1px solid #00FFFF !important;
    }}
    div[data-baseweb="tag"] span {{
        color: #FFFFFF !important;
    }}
    /* ドロップダウンメニューの中身 */
    div[role="listbox"] ul {{
        background-color: #111111 !important;
    }}
    div[role="option"] {{
        color: #EEEEEE !important;
        background-color: #111111 !important;
    }}
    /* 選択肢の文字色強制 */
    .stMultiSelect span {{
        color: #FFFFFF !important;
    }}

    /* フッター */
    .footer {{
        position: fixed; left: 0; bottom: 0; width: 100%;
        background-color: #000000; color: #555 !important;
        text-align: center; padding: 5px; font-size: 12px;
        border-top: 1px solid #333; z-index: 100; font-family: sans-serif;
    }}
    .block-container {{ padding-bottom: 80px; }}
    </style>
    <div class="footer">SYSTEM: {APP_TITLE} | ARCHITECT: SHINGO KUSANO | {COMPANY_NAME}</div>
    """, unsafe_allow_html=True)

# ==========================================
# 1. KUSANO_BRAIN (Expert Logic V2.5: FCCS Instructor Edition)
# ==========================================
KUSANO_BRAIN = """
あなたは、高度救命救急センターの「統括司令塔（Medical Commander）」としての役割を持つAI「草野」です。
**「多職種連携」**と**「攻めの医療」**を前提とし、FCCSインストラクターレベルの生理学的根拠に基づいた指示を出してください。

【プロフェッショナルの役割定義】
1. **【医師 (MD)】**: 診断、治療方針決定、侵襲的手技。
2. **【看護師 (NS)】**: 微細な変化の検知、鎮静・鎮痛評価、家族ケア。
3. **【臨床工学技士 (CE)】**: 機器設定の最適化。Recirculationおよび**O2ERの監視**。
4. **【薬剤師 (Ph)】**: TDM、配合変化確認。
5. **【コメディカル (RD/PT)】**: 早期栄養・早期離床提案。

【絶対遵守ルール & 臨床判断ロジック】
1. **用語**: 思考・検索は英語で行うが、出力時は「AKI (急性腎障害)」のように日本語を併記せよ。

2. **SvO2高値 (High SvO2 > 80%) の鑑別ロジック (The 3 Patterns)**:
   - 脱血側 (Pre-membrane) のSvO2が **>80%** と高値の場合、「酸素十分」と短絡的に判断せず、以下の3パターンをpHおよびLactateとのクロス分析で鑑別せよ。
   
   - **パターンA: Recirculation (再循環)**
     - 状況: VV-ECMO導入直後、高流量、Lactate高値。
     - アクション: **「流量を上げろ」等の単純指示は禁止**。CEへカニューレ位置調整、回転数適正化（下げて効率を見る）を指示せよ。
     
   - **パターンB: Left Shift (酸素解離曲線の左方移動)**
     - 判定基準: **「pH > 7.45 (アルカレミア)」** または **「低体温」** がある場合。
     - 病態: ヘモグロビンの酸素親和性が高まり、末梢で酸素を離さない(Unloading Failure)。見かけ上のSvO2上昇。
     - アクション: 分時換気量の調整によるpH補正、復温。
     
   - **パターンC: Tissue Dysoxia (組織酸素利用障害)**
     - 判定基準: **「Recirculationなし」かつ「pHは正常〜アシデミア」なのに「Lactate上昇」**。
     - 病態: Sepsis末期、ミトコンドリア不全、Luxury Perfusion。**最も危険な状態**。
     - アクション: もはやDO2を上げるだけでは無意味。「代謝の抑制（低体温・深鎮静）」や「ミトコンドリア保護」といった次元の違うアプローチを提案せよ。

3. **輸血戦略 (Expert Opinion)**:
   - 単にHb値や出血量だけで輸血を決定してはならない。**DO2/VO2バランス**を指標とせよ。
   - **トリガー**: 「SvO2 < 70% (Recirculation除外後)」、「O2ER > 30%」、または「Lactate Clearanceの停滞」を確認した時に輸血を推奨せよ。

4. **臨床ジレンマと「攻め」の解決策**:
   - 右心不全 (Cor Pulmonale) には、ノルアドレナリン単独を避け、**バソプレシン併用**や**ドブタミン**を考慮せよ。
   - **Prone Positioning (腹臥位療法)**: ARDSによる重度低酸素と右心負荷の悪循環があれば、リスクを承知でProneを**「First Choice」**として推奨せよ。

5. **回答スタイル**:
   - 結論ファースト。「検討する」ではなく「準備せよ」「開始せよ」と断定する。

【回答構成】
---SECTION_PLAN_EMERGENCY---
**【🚨 最優先・緊急アクション (Do Now)】**
生命維持のための即時介入。High SvO2時の「3パターン鑑別結果」もここへ記述。

---SECTION_AI_OPINION---
**【🧠 病態推論・クロスオーバー分析 (Art of ICU)】**
- トレンドデータの乖離（SvO2, pH, Lactateのトライアングル分析）。
- **攻めの治療提案**。

---SECTION_PLAN_ROUTINE---
**【✅ 継続管理・詳細プラン (Do Next)】**
栄養、リハ、感染管理。

---SECTION_FACT---
**【📚 エビデンス・根拠】**
"""

# ==========================================
# 2. データ管理 & Session State
# ==========================================
if 'patient_db' not in st.session_state:
    st.session_state['patient_db'] = {}
if 'demo_active' not in st.session_state:
    st.session_state['demo_active'] = False

current_patient_id = None 
selected_model_name = None

# ==========================================
# 3. サイドバー
# ==========================================
with st.sidebar:
    st.title("⚙️ SYSTEM CONFIG")
    st.caption("STATUS: PROTOTYPE v2.6 (FCCS)")

    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("🔑 SYSTEM CONNECTED")
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
            selected_model_name = st.selectbox("AI ENGINE", model_list, index=default_index)
        except: st.error("Model Error")

    st.markdown("---")
    is_demo = st.checkbox("シミュレーション・モード起動", value=False)
    
    if is_demo:
        current_patient_id = "DEMO-CASE-001"
        st.error(f"⚠️ SIMULATION MODE: {current_patient_id}")
        if not st.session_state['demo_active']:
            st.session_state['patient_db'][current_patient_id] = [
                {"Time": "10:00", "P/F": 120, "DO2": 450, "O2ER": 35, "Lactate": 4.5, "Hb": 9.0, "pH": 7.25, "SvO2": 65, "Na": 138, "Cl": 105, "HCO3": 22, "Alb": 3.8},
                {"Time": "11:00", "P/F": 110, "DO2": 420, "O2ER": 40, "Lactate": 5.2, "Hb": 8.8, "pH": 7.21, "SvO2": 62, "Na": 137, "Cl": 108, "HCO3": 18, "Alb": 3.7},
                {"Time": "12:00", "P/F": 95,  "DO2": 380, "O2ER": 45, "Lactate": 6.8, "Hb": 8.5, "pH": 7.15, "SvO2": 58, "Na": 135, "Cl": 110, "HCO3": 14, "Alb": 3.5}
            ]
            st.session_state['demo_active'] = True
    else:
        st.session_state['demo_active'] = False
        patient_id_input = st.text_input("🆔 PATIENT ID", value="TEST1", max_chars=10)
        if patient_id_input:
            if not re.match(r'^[a-zA-Z0-9]+$', patient_id_input):
                st.error("⚠️ Alphanumeric Only")
            else:
                current_patient_id = patient_id_input.upper()
                st.success(f"LOGIN: {current_patient_id}")
    
    if current_patient_id and not is_demo:
        st.markdown("---")
        if st.button("🗑️ CLEAR HISTORY", key="del_btn"):
            st.session_state['patient_db'][current_patient_id] = []
            st.rerun()

# ==========================================
# 4. メイン画面
# ==========================================
st.title(f"🫀 {APP_TITLE}")

if not current_patient_id:
    st.info("👈 Please enter Patient ID or Start Demo Mode.")
    st.stop()

# デモ用テキスト
default_hist = ""
default_lab = ""
if is_demo:
    default_hist = "60代男性。重症肺炎によるARDS。VV-ECMO導入後だが、Sepsis進行により循環動態不安定。Lac上昇傾向。"
    default_lab = "pH 7.15, PaO2 55, PaCO2 60, Lac 6.8, BE -10, Na 135, K 4.5, Cl 100"

tab1, tab2 = st.tabs(["📝 CLINICAL DIAGNOSIS", "📈 VITAL TRENDS"])

# === TAB 2: トレンド管理 (カスタマイズグラフ実装) ===
with tab2:
    st.markdown("#### 🏥 Bedside Monitor Input")
    
    # 入力フォーム
    c1, c2, c3 = st.columns(3)
    pao2 = c1.number_input("PaO2", step=1.0)
    fio2 = c1.number_input("FiO2 (%)", step=1.0)
    lac = c1.number_input("Lactate (mmol/L)", step=0.1)
    
    hb = c2.number_input("Hb (g/dL)", step=0.1)
    co = c2.number_input("CO (L/min)", step=0.1)
    spo2 = c2.number_input("SpO2 (%)", step=1.0)
    
    ph = c3.number_input("pH", step=0.01)
    svo2 = c3.number_input("SvO2 (Pre) %", step=1.0, help="VV-ECMO時はRecirculationに注意")

    # 電解質
    e1, e2, e3, e4 = st.columns(4)
    na = e1.number_input("Na", step=1.0)
    cl = e2.number_input("Cl", step=1.0)
    hco3 = e3.number_input("HCO3", step=0.1)
    alb = e4.number_input("Alb", step=0.1)

    # 計算ロジック
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
        if alb: c_ag = ag + 2.5 * (4.0 - alb)

    # プレビュー
    if pf or do2 or o2er or ag:
        st.markdown("---")
        cols = st.columns(4)
        cols[0].metric("P/F", f"{pf:.0f}" if pf else "-")
        cols[1].metric("DO2", f"{do2:.0f}" if do2 else "-")
        cols[2].metric("O2ER", f"{o2er:.1f}%" if o2er else "-")
        cols[3].metric("AG(c)", f"{c_ag:.1f}" if c_ag else (f"{ag:.1f}" if ag else "-"))

    if st.button("💾 SAVE DATA"):
        if current_patient_id not in st.session_state['patient_db']: 
            st.session_state['patient_db'][current_patient_id] = []
        
        record = {
            "Time": datetime.now().strftime("%H:%M:%S"),
            "P/F": pf, "DO2": do2, "O2ER": o2er, 
            "Lactate": lac, "Hb": hb, "pH": ph, "SvO2": svo2,
            "AG": c_ag if c_ag else ag,
            "Na": na, "Cl": cl, "HCO3": hco3, "Alb": alb,
            "CO": co, "SpO2": spo2, "PaO2": pao2, "FiO2": fio2
        }
        st.session_state['patient_db'][current_patient_id].append(record)
        st.rerun()
    
    # --- グラフ描画 (全項目選択可能版) ---
    hist = st.session_state['patient_db'].get(current_patient_id, [])
    if hist:
        df = pd.DataFrame(hist)
        
        # 入力可能な全項目リスト
        all_possible_cols = [
            "P/F", "DO2", "O2ER", "Lactate", "Hb", "pH", "SvO2", "AG",
            "Na", "Cl", "HCO3", "Alb", "CO", "SpO2", "PaO2", "FiO2"
        ]
        
        # データフレーム内の数値変換
        for col in all_possible_cols:
            if col not in df.columns: df[col] = None
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        st.markdown("### 📉 CUSTOM TREND ANALYSIS")
        
        # データが存在するカラムのみを選択肢として表示
        available_options = [c for c in all_possible_cols if df[c].notna().any()]
        
        # デフォルト選択 (草野スペシャル)
        default_cols = [c for c in ["SvO2", "Lactate", "O2ER"] if c in available_options]
        
        selected_cols = st.multiselect(
            "👇 表示したい項目を選択 (Select Parameters)",
            options=available_options,
            default=default_cols
        )
        
        if selected_cols:
            st.line_chart(df.set_index("Time")[selected_cols])
            st.caption(f"Displaying: {', '.join(selected_cols)}")
        else:
            st.info("上のボックスから表示したい項目を選んでください。")

# === TAB 1: 総合診断 ===
with tab1:
    col1, col2 = st.columns(2)
    hist_text = col1.text_area("Patient History", value=default_hist, height=150)
    lab_text = col1.text_area("Lab Data / Parameters", value=default_lab, height=150)
    up_file = col2.file_uploader("Upload Image", accept_multiple_files=True)

    st.markdown("---")
    if st.button("🚀 EXECUTE AI DIAGNOSIS", type="primary"):
        if not api_key:
            st.error("⚠️ NO API KEY")
        else:
            trend_str = "No Data"
            hist = st.session_state['patient_db'].get(current_patient_id, [])
            if hist: trend_str = pd.DataFrame(hist).tail(5).to_markdown(index=False)
            
            # 1. Search
            search_context = ""
            try:
                model_kw = genai.GenerativeModel(model_name=selected_model_name)
                kw_prompt = f"Extract 3 medical keywords (space separated) for ICU patient search:\n{hist_text[:200]}\n{lab_text[:200]}"
                kw_res = model_kw.generate_content(kw_prompt)
                search_key = kw_res.text.strip()
                
                with st.spinner(f"🌐 Searching Evidence: {search_key}..."):
                    with DDGS() as ddgs:
                        results = list(ddgs.text(f"{search_key} guideline intensive care", region='jp-jp', max_results=3))
                        for r in results: search_context += f"Title: {r['title']}\nURL: {r['href']}\nBody: {r['body']}\n\n"
            except Exception as e: search_context = f"Search Error: {e}"

            # 2. Prompt
            prompt = f"""
            Analyze the ICU patient data.
            【History】{hist_text}
            【Labs】{lab_text}
            【Trend Data】{trend_str}
            【Search Evidence】{search_context}
            """
            
            content = [prompt]
            if up_file:
                for f in up_file: content.append(Image.open(f))

            try:
                model = genai.GenerativeModel(model_name=selected_model_name, system_instruction=KUSANO_BRAIN)
                with st.spinner("🧠 KUSANO_BRAIN is thinking..."):
                    res = model.generate_content(content)
                
                # Result Parsing
                raw = res.text
                parts_emer = raw.split("---SECTION_PLAN_EMERGENCY---")
                parts_ai   = raw.split("---SECTION_AI_OPINION---")
                parts_rout = raw.split("---SECTION_PLAN_ROUTINE---")
                parts_fact = raw.split("---SECTION_FACT---")

                st.success("✅ Analysis Complete")

                if len(parts_emer) > 1:
                    st.error(f"🚨 **EMERGENCY ACTION (Do Now)**\n\n{parts_emer[1].split('---SECTION')[0].strip()}", icon="⚡")
                if len(parts_ai) > 1:
                    st.warning(f"🤔 **CLINICAL REASONING (The Art of ICU)**\n\n{parts_ai[1].split('---SECTION')[0].strip()}", icon="🧠")
                if len(parts_rout) > 1:
                    st.info(f"✅ **MANAGEMENT PLAN (Do Next)**\n\n{parts_rout[1].split('---SECTION')[0].strip()}", icon="📋")
                if len(parts_fact) > 1:
                    with st.expander("📚 Evidence & References"):
                        st.markdown(parts_fact[1].split('---SECTION')[0].strip())
                        if search_context and "Error" not in search_context:
                             st.divider()
                             st.text("Raw Search Results:\n" + search_context)
                
                if "---SECTION" not in raw: st.write(raw)

            except Exception as e: st.error(f"System Error: {e}")
