import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
import re
import json
from datetime import datetime
from duckduckgo_search import DDGS

# ==========================================
# 0. アプリ設定 & MERA仕様デザイン (Dark Medical Cockpit V2.1)
# ==========================================
COMPANY_NAME = "K's tech works. (K&G solution)"
APP_TITLE = "Super Clinical Decision Support [PRO]"

st.set_page_config(page_title=APP_TITLE, layout="wide", page_icon="🫀")

# --- CSS: 医療用モニター風のUI/UX（視認性修正版） ---
st.markdown(f"""
    <style>
    /* 全体背景：漆黒 */
    .stApp {{
        background-color: #000000;
        color: #FFFFFF;
    }}
    
    /* 文字が見えない問題の修正：全テキスト要素を強制的に白くする */
    h1, h2, h3, h4, h5, h6, p, li, span, div {{
        color: #E0E0E0 !important;
    }}
    
    /* 入力フォームのラベルをハッキリ白く */
    label, .stTextInput label, .stNumberInput label, .stTextArea label, .stFileUploader label, .stSelectbox label {{
        color: #FFFFFF !important;
        font-weight: bold !important;
    }}
    
    /* サイドバーの修正 */
    [data-testid="stSidebar"] {{
        background-color: #111111;
        border-right: 1px solid #333;
    }}
    [data-testid="stSidebar"] * {{
        color: #CCCCCC !important;
    }}

    /* メトリックカード（数値表示部） */
    div[data-testid="metric-container"] {{
        background-color: #1E1E1E;
        border: 1px solid #444;
        padding: 10px;
        border-radius: 5px;
        box-shadow: 0 0 10px rgba(0, 255, 255, 0.1);
    }}
    div[data-testid="metric-container"] label {{
        color: #AAAAAA !important; /* ラベルは少し暗くして数値を際立たせる */
    }}
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {{
        color: #00FFFF !important; /* 数値はネオンシアン */
    }}
    
    /* 入力ボックスの中身を見やすく（ダークグレー背景＋白文字） */
    .stNumberInput input, .stTextInput input, .stTextArea textarea {{
        background-color: #222222 !important;
        color: #FFFFFF !important;
        border: 1px solid #555 !important;
    }}
    
    /* アラートの見栄え */
    .stAlert {{
        background-color: #330000;
        border: 1px solid #FF0000;
    }}
    .stAlert * {{
        color: #FFDDDD !important;
    }}
    
    /* フッター */
    .footer {{
        position: fixed; left: 0; bottom: 0; width: 100%;
        background-color: #000000; color: #555 !important;
        text-align: center; padding: 5px; font-size: 12px;
        border-top: 1px solid #333; z-index: 100; font-family: sans-serif;
    }}
    .footer * {{ color: #555 !important; }}
    .block-container {{ padding-bottom: 80px; }}
    </style>
    <div class="footer">SYSTEM: {APP_TITLE} | ARCHITECT: SHINGO KUSANO | {COMPANY_NAME}</div>
    """, unsafe_allow_html=True)

# ==========================================
# 1. KUSANO_BRAIN (オリジナルを維持)
# ==========================================
KUSANO_BRAIN = """
あなたは、高度救命救急センターの「統括司令塔（Medical Commander）」としての役割を持つAI「草野」です。
**「多職種連携（Interprofessional Work）」**を前提とし、各専門職の能力を最大限に引き出す指示を出してください。

【プロフェッショナルの役割定義】
以下の役割に基づき、単なる作業指示ではなく「評価・提案・管理」を含めた指示を行うこと。
1. **【医師 (MD)】**: 診断、治療方針の最終決定、侵襲的手技、家族へのIC。
2. **【看護師 (NS)】**: 患者の微細な変化（顔色、苦痛）の早期検知、鎮静・鎮痛評価、家族ケア、感染管理。
3. **【臨床工学技士 (CE)】**: 機器（人工呼吸器, VA-ECMO, VV-ECMO, CRRT）を用いた生体機能の代行と最適化。**LV Unloading (左室負荷軽減)**や**右心保護戦略**の観点から設定変更を提案。
4. **【薬剤師 (Ph)】**: 腎・肝機能に応じた投与設計(TDM)、配合変化確認、抗菌薬適正使用介入。
5. **【管理栄養士 (RD) / 理学療法士 (PT)】**: 早期経腸栄養の提案、早期離床・リハビリ計画。

【絶対遵守ルール】
0. **用語の標準化と可読性**:
   - 検索精度を高めるため思考・検索は国際標準用語で行うが、**出力時は「AKI (急性腎障害)」のように日本語を併記**し、全職種に伝わるようにすること。
   - 例: PCPS → **VA-ECMO (PCPS)**, 人工呼吸器 → **Mechanical Ventilation (人工呼吸器)**, 急性腎不全 → **AKI (急性腎障害)**, 敗血症 → **Sepsis-3**

1. **エビデンス・ファースト (最重要)**:
   - 検索結果（Search Results）の内容を重視し、**ハルシネーション（嘘）を徹底的に排除**せよ。
   - 根拠となるガイドラインや文献がない場合は、正直に「データ不足」と伝えること。

2. **臨床ジレンマと「攻め」の解決策**:
   - 「Aを立てればBが立たず」の状況で、単に様子を見るのではなく**「解決するための追加介入」**を提案せよ。
   - 例: 「PCPSで後負荷が増えるなら、**IABP/Impella追加でLV Unloading**せよ」
   - 例: 「循環が不安定でも溢水が著明なら、**昇圧剤を増量してでもAggressive Fluid Removal (積極的除水)**せよ」
   - 例: 「COPD/ARDSで右心負荷が高い場合、ノルアドレナリン単独による後負荷増大を避け、**バソプレシン併用や強心薬(ドブタミン)**を考慮せよ」
   - 例: 「胃残が多いなら、**幽門後栄養 (Post-pyloric Feeding)**チューブを留置して栄養を開始せよ」

3. **安全と禁忌 (Crucial Judgment)**:
   - **Post-intubation Hypotension (挿管後ショック)**: 挿管直後の血圧低下は必発と予測し、事前の輸液負荷と昇圧剤スタンバイを「絶対指示」とせよ。
   - **【例外規定】RV-Protective Ventilation (右心保護換気戦略)**:
     - 原則として不安定な循環動態での体位変換は禁忌である。
     - **しかし、右心不全 (Cor Pulmonale) の主因が無気肺・HPVであると判断される場合に限り、** リスクを承知で **「Open Lung Strategy (高PEEP / Recruitment)」** および **「Prone Positioning (腹臥位療法)」** を推奨せよ。物理的にPVRを下げることこそが救命の鍵である。
   - 上記以外での「やってはいけないこと (Do Not)」は明確に警告せよ。

4. **現場のリアリティ**:
   - スマホ閲覧を想定し、結論ファーストで簡潔に。「検討する」ではなく「準備する」「開始する」と断定せよ。

【回答セクション構成】

---SECTION_PLAN_EMERGENCY---
**【🚨 最優先・緊急アクション (Do Now)】**
生命維持のため、今この瞬間に動くべきタスク。主語（医師、看護師、CE、薬剤師）を明確に。

---SECTION_AI_OPINION---
**【🧠 病態推論・クロスオーバー分析】**
- トレンドデータの乖離から読み取れる隠れた病態。
- 負の連鎖の特定。
- **「攻めの治療」の提案（Unloading, RV保護, PIH対策等）**。
- **⚠️ Do Not（禁忌と、その「戦略的例外」）**。

---SECTION_PLAN_ROUTINE---
**【✅ 継続管理・詳細プラン (Do Next)】**
チーム全体（栄養、リハ、薬剤調整）で取り組むべき管理方針。

---SECTION_FACT---
**【📚 エビデンス・根拠】**
検索結果に基づくガイドラインや文献の引用。
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
# 3. サイドバー (デモモード搭載)
# ==========================================
with st.sidebar:
    st.title("⚙️ SYSTEM CONFIG")
    st.caption("STATUS: PROTOTYPE v2.1")

    # --- API Key Logic ---
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("🔑 SYSTEM CONNECTED")
    except:
        api_key = st.text_input("Gemini API Key", type="password")
    
    if api_key:
        genai.configure(api_key=api_key)
        try:
            model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            # Proモデルを優先
            default_index = 0
            for i, m_name in enumerate(model_list):
                if "gemini-1.5-pro" in m_name:
                    default_index = i
                    break
            selected_model_name = st.selectbox("AI ENGINE", model_list, index=default_index)
        except: st.error("Model Connection Error")

    st.markdown("---")
    
    # --- デモモード切替スイッチ ---
    st.markdown("### 🛑 EMERGENCY DEMO")
    is_demo = st.checkbox("シミュレーション・モード起動", value=False, help="プレゼン用に重症患者データをロードします")
    
    if is_demo:
        current_patient_id = "DEMO-CASE-001"
        st.error(f"⚠️ SIMULATION MODE: {current_patient_id}")
        # デモ用データの注入 (1回だけ)
        if not st.session_state['demo_active']:
            st.session_state['patient_db'][current_patient_id] = [
                {"Time": "10:00", "P/F": 120, "DO2": 450, "O2ER": 35, "Lactate": 4.5, "Hb": 9.0, "pH": 7.25, "AG": 18},
                {"Time": "11:00", "P/F": 110, "DO2": 420, "O2ER": 40, "Lactate": 5.2, "Hb": 8.8, "pH": 7.21, "AG": 20},
                {"Time": "12:00", "P/F": 95,  "DO2": 380, "O2ER": 45, "Lactate": 6.8, "Hb": 8.5, "pH": 7.15, "AG": 24}
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

    # --- データ操作 ---
    if current_patient_id and not is_demo:
        st.markdown("---")
        if st.button("🗑️ CLEAR HISTORY", key="del_btn"):
            st.session_state['patient_db'][current_patient_id] = []
            st.rerun()

# ==========================================
# 4. メイン画面 (モニターレイアウト)
# ==========================================
st.title(f"🫀 {APP_TITLE}")

if not current_patient_id:
    st.info("👈 Please enter Patient ID or Start Demo Mode.")
    st.stop()

# デモ用：病歴テキストの自動セット
default_hist = ""
default_lab = ""
if is_demo:
    default_hist = "60代男性。重症肺炎によるARDS。VV-ECMO導入後だが、Sepsis進行により循環動態不安定。Lac上昇傾向。右心負荷所見あり。"
    default_lab = "pH 7.15, PaO2 55, PaCO2 60, Lac 6.8, BE -10, Na 135, K 4.5, Cl 100, BNP 800"

tab1, tab2 = st.tabs(["📝 CLINICAL DIAGNOSIS", "📈 VITAL TRENDS"])

# === TAB 2: トレンド管理 (数値入力 & グラフ) ===
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
    svo2 = c3.number_input("SvO2 (%)", step=1.0)

    st.markdown("#### 🧪 Electrolytes (for Anion Gap)")
    e1, e2, e3, e4 = st.columns(4)
    na = e1.number_input("Na", step=1.0)
    cl = e2.number_input("Cl", step=1.0)
    hco3 = e3.number_input("HCO3", step=0.1)
    alb = e4.number_input("Alb", step=0.1)

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
        if alb: c_ag = ag + 2.5 * (4.0 - alb)

    # リアルタイム計算プレビュー
    if pf or do2 or o2er or ag:
        st.markdown("---")
        cols = st.columns(4)
        cols[0].metric("P/F Ratio", f"{pf:.0f}" if pf else "-")
        cols[1].metric("DO2", f"{do2:.0f}" if do2 else "-")
        cols[2].metric("O2ER", f"{o2er:.1f}%" if o2er else "-")
        cols[3].metric("Anion Gap(corr)", f"{c_ag:.1f}" if c_ag else (f"{ag:.1f}" if ag else "-"))

    if st.button("💾 SAVE DATA"):
        if current_patient_id not in st.session_state['patient_db']: 
            st.session_state['patient_db'][current_patient_id] = []
        
        record = {
            "Time": datetime.now().strftime("%H:%M:%S"),
            "P/F": pf, "DO2": do2, "O2ER": o2er, 
            "Lactate": lac, "Hb": hb, "pH": ph, "AG": c_ag if c_ag else ag
        }
        st.session_state['patient_db'][current_patient_id].append(record)
        st.rerun()
    
    # --- グラフ描画 ---
    hist = st.session_state['patient_db'].get(current_patient_id, [])
    if hist:
        df = pd.DataFrame(hist)
        target_cols = ["P/F", "DO2", "O2ER", "Lactate", "Hb", "pH", "AG"]
        for col in target_cols:
            if col not in df.columns: df[col] = None
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        st.markdown("### 📉 TREND ANALYSIS")
        g1, g2 = st.columns(2)
        with g1:
            st.caption("Respiratory / Metabolic Load")
            available_cols1 = [c for c in ["P/F", "O2ER", "Lactate"] if df[c].notna().any()]
            if available_cols1: st.line_chart(df.set_index("Time")[available_cols1])
        with g2:
            st.caption("Circulation / Acid-Base")
            available_cols2 = [c for c in ["AG", "pH", "DO2"] if df[c].notna().any()]
            if available_cols2: st.line_chart(df.set_index("Time")[available_cols2])

# === TAB 1: 総合診断 (DuckDuckGo + Gemini Pro) ===
with tab1:
    col1, col2 = st.columns(2)
    hist_text = col1.text_area("Patient History", value=default_hist, height=150)
    lab_text = col1.text_area("Lab Data / Parameters", value=default_lab, height=150)
    up_file = col2.file_uploader("Upload Image (X-ray, ECG, Monitor)", accept_multiple_files=True)

    st.markdown("---")
    if st.button("🚀 EXECUTE AI DIAGNOSIS", type="primary"):
        if not api_key:
            st.error("⚠️ NO API KEY")
        else:
            # トレンドデータの取得
            trend_str = "No Data"
            hist = st.session_state['patient_db'].get(current_patient_id, [])
            if hist: 
                trend_str = pd.DataFrame(hist).tail(5).to_markdown(index=False)
            
            # --- 1. DuckDuckGo Search ---
            search_context = ""
            try:
                # 検索ワード生成
                model_kw = genai.GenerativeModel(model_name=selected_model_name)
                kw_prompt = f"Extract 3 medical keywords (space separated) for search based on this context for ICU patient:\n{hist_text[:200]}\n{lab_text[:200]}"
                kw_res = model_kw.generate_content(kw_prompt)
                search_key = kw_res.text.strip()
                
                with st.spinner(f"🌐 Searching Evidence: {search_key}..."):
                    with DDGS() as ddgs:
                        # 英語論文も検索対象にするためregion指定を外しても良いが、まずは日本語で精度確保
                        results = list(ddgs.text(f"{search_key} guideline intensive care", region='jp-jp', max_results=3))
                        for r in results: search_context += f"Title: {r['title']}\nURL: {r['href']}\nBody: {r['body']}\n\n"
            except Exception as e:
                search_context = f"Search Error: {e}"

            # --- 2. AI Prompting ---
            prompt = f"""
            Analyze the following ICU patient data and provide clinical decision support.
            
            【History】{hist_text}
            【Labs】{lab_text}
            【Trend Data (Last 5 points)】{trend_str}
            【Search Evidence】{search_context}
            """
            
            content = [prompt]
            if up_file:
                for f in up_file: content.append(Image.open(f))

            try:
                # 3. AI Execution
                model = genai.GenerativeModel(model_name=selected_model_name, system_instruction=KUSANO_BRAIN)
                with st.spinner("🧠 KUSANO_BRAIN is thinking..."):
                    res = model.generate_content(content)
                
                # --- Result Parsing ---
                raw = res.text
                parts_emer = raw.split("---SECTION_PLAN_EMERGENCY---")
                parts_ai   = raw.split("---SECTION_AI_OPINION---")
                parts_rout = raw.split("---SECTION_PLAN_ROUTINE---")
                parts_fact = raw.split("---SECTION_FACT---")

                st.success("✅ Analysis Complete")

                if len(parts_emer) > 1:
                    emer_content = parts_emer[1].split("---SECTION")[0].strip()
                    st.error(f"🚨 **EMERGENCY ACTION (Do Now)**\n\n{emer_content}", icon="⚡")

                if len(parts_ai) > 1:
                    ai_content = parts_ai[1].split("---SECTION")[0].strip()
                    st.warning(f"🤔 **CLINICAL REASONING (The Art of ICU)**\n\n{ai_content}", icon="🧠")

                if len(parts_rout) > 1:
                    rout_content = parts_rout[1].split("---SECTION")[0].strip()
                    st.info(f"✅ **MANAGEMENT PLAN (Do Next)**\n\n{rout_content}", icon="📋")

                if len(parts_fact) > 1:
                    fact_content = parts_fact[1].split("---SECTION")[0].strip()
                    with st.expander("📚 Evidence & References"):
                        st.markdown(fact_content)
                        if search_context and "Error" not in search_context:
                             st.divider()
                             st.text("Raw Search Results:\n" + search_context)

                # セクション分割がうまくいかなかった場合のフォールバック
                if "---SECTION" not in raw: st.write(raw)
                
                st.caption("⚠️ This system is a prototype for clinical decision support. Final judgment by MD is required.")

            except Exception as e:
                st.error(f"System Error: {e}")
