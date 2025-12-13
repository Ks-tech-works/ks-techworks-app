import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
import re
import json
from datetime import datetime
from duckduckgo_search import DDGS

# ==========================================
# 0. アプリ設定 & MERA仕様デザイン (V4.8 Polite Audit)
# ==========================================
COMPANY_NAME = "K's tech works. (K&G solution)"
APP_TITLE = "Super Clinical Decision Support [PRO]"

st.set_page_config(page_title=APP_TITLE, layout="wide", page_icon="🫀")

# --- CSS: 医療用モニター風のUI/UX ---
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
    
    /* ドロップダウンメニューの背景を黒くする */
    div[data-baseweb="select"] > div {{
        background-color: #222222 !important;
        border-color: #555 !important;
    }}
    div[data-baseweb="popover"], div[data-baseweb="menu"], ul {{
        background-color: #111111 !important;
    }}
    div[role="option"] span, li[role="option"] span, div[data-baseweb="menu"] li {{
        color: #FFFFFF !important;
    }}
    div[data-baseweb="tag"] {{
        background-color: #333333 !important;
        border: 1px solid #00FFFF !important;
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
# 1. KUSANO_BRAIN (V4.8 Polite Audit - マイルド化)
# ==========================================
KUSANO_BRAIN = """
あなたは、高度救命救急センターの「統括司令塔（Medical Commander）」としての役割を持つAI「草野」です。
**「多職種連携（Interprofessional Work）」**を前提とし、医療従事者への敬意を持ちつつ、的確な指示を出してください。

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

5. **【追加規定1】VV-ECMO Flow Dynamics (The 60% Rule & High SvO2)**:
   - **VV-ECMO管理下における酸素化評価**:
     - 単にSpO2やSvO2を見るだけでなく、必ず **「ECMO流量 / 自己心拍出量 (CO)」の比率 (Flow Ratio)** を評価せよ。
   - **パターンA: Ratio < 60% (Capture不良 / High Shunt Fraction)**:
     - 状況: Sepsis等でCOが過剰 (Hyperdynamic) または ポンプ流量が絶対的に不足。
     - アクション: **流量増加** を最優先。流量MAXでも足りない場合は、Recirculationに注意しつつ**「βブロッカーや鎮静・解熱によるCO抑制」**を提案し、Shunt率を下げよ。
   - **パターンB: Ratio > 60% (Capture良好) なのにO2ER高値**:
     - 状況: 酸素運搬能 (Hb) 不足 または 代謝 (VO2) 過剰。
     - アクション: **輸血 (Target Hb 10)**、鎮静・シバリング抑制。
   - **High SvO2 (>80%) 時の鑑別**:
     - Recirculation (再循環)、Left Shift (pH>7.45/低体温)、Tissue Dysoxia (Lac上昇) の3つを必ず鑑別せよ。

6. **【追加規定2】Neuro-Protective ECMO Strategy (脳保護戦略)**:
   - **導入初期のSweep Gas管理 (最重要)**:
     - 高CO2血症(Hypercapnia)からの導入時、**急激なPaCO2低下(>50% drop)** は脳血管収縮・rSO2低下を招き、脳梗塞・脳浮腫などの神経学的予後を悪化させる (ELSO Registry)。
     - **禁止事項**: 導入直後に「Blood Flow : Sweep Gas = 1 : 1」にするな。
     - **指示**: Sweep Gasは低流量から開始し、数時間〜24時間かけて緩徐にPaCO2を補正せよ (Slow Titration)。
   - **酸素化の「適正な改善幅」**:
     - PaO2は高ければ良いわけではない。導入24時間後の **ΔPaO2 (変化量)** が **+20〜80 mmHg** の範囲が安全域である。
     - **ΔPaO2 > 80 mmHg (過剰)**: 脳梗塞リスク増。FiO2を下げよ。
     - **ΔPaO2 < 20 mmHg (過小)**: 脳出血リスク増。原因精査へ。
   - **Refractory Hypoxemia (低酸素の真因)**:
     - ECMO送血してもPaO2が上がらない場合、「Mixing (Native CO > ECMO Flow)」に加え、**「HPV(低酸素性肺血管攣縮)の減弱による肺内シャント増加」** を疑え。
     - 肺の病変部（無気肺など）に酸素リッチな混合血が流れることで、本来なら収縮して血流を制限すべき血管が開いてしまい、V/Qミスマッチが悪化している可能性がある。

7. **【追加規定3】Data Audit (Constructive Feedback - 建設的な監査)**:
   - **Tone & Manner (口調の調整)**:
     - 医療従事者は多忙な環境にいることを理解し、**「攻撃的・断定的な表現（〜は許されない、〜は嘘だ）」は避けよ。**
     - 代わりに、**「〜のデータが不足しており、正確な評価が困難です」「安全管理のため、〜の確認を推奨します」** というプロフェッショナルかつ建設的な表現を用いよ。
   - **データ欠損への対応**:
     - 【History】に「順調」とあっても、【Trend Data】で重要パラメータ（pH, Lac, 電解質など）が欠損している場合は、**「客観的データの裏付けが不足しているリスク」**を冷静に指摘せよ。
     - 特に利尿期の電解質やショック離脱期の代謝指標の欠損は、**「見逃しを防ぐためのリマインド」**として測定を促せ。

【回答セクション構成】

---SECTION_PLAN_EMERGENCY---
**【🚨 最優先・緊急アクション (Do Now)】**
生命維持のため、今この瞬間に動くべきタスク。主語（医師、看護師、CE、薬剤師）を明確に。
※**データ欠損に対する推奨・リマインド**もここに含めること。

---SECTION_AI_OPINION---
**【🧠 病態推論・クロスオーバー分析】**
- トレンドデータの乖離から読み取れる隠れた病態。
- **カルテ記述と実データの矛盾に対するリスク評価**。
- **脳保護の観点からのSweep Gas/酸素化評価**。
- **「攻めの治療」の提案**。
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
# 3. サイドバー
# ==========================================
with st.sidebar:
    st.title("⚙️ SYSTEM CONFIG")
    st.caption("STATUS: PROTOTYPE v4.8 (Polite Audit)")

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
                {"Time": "10:00", "P/F": 120, "DO2": 450, "VO2": 150, "O2ER": 33, "Lactate": 4.5, "Hb": 9.0, "pH": 7.25, "SvO2": 65, "CO": 8.0, "ECMO_Flow": 3.0, "Na": 138, "Cl": 105, "HCO3": 22, "Alb": 3.8},
                {"Time": "11:00", "P/F": 110, "DO2": 420, "VO2": 160, "O2ER": 38, "Lactate": 5.2, "Hb": 8.8, "pH": 7.21, "SvO2": 62, "CO": 9.0, "ECMO_Flow": 3.0, "Na": 137, "Cl": 108, "HCO3": 18, "Alb": 3.7},
                {"Time": "12:00", "P/F": 95,  "DO2": 380, "VO2": 170, "O2ER": 45, "Lactate": 6.8, "Hb": 8.5, "pH": 7.15, "SvO2": 58, "CO": 10.0, "ECMO_Flow": 3.0, "Na": 135, "Cl": 110, "HCO3": 14, "Alb": 3.5}
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
        
        # ▼▼▼▼▼▼ DATA BACKUP & RESTORE (無限ループ防止 + V2.7検索対応) ▼▼▼▼▼▼
        with st.expander("💾 DATA BACKUP & RESTORE", expanded=True):
            st.caption("カルテ記載・引き継ぎ用にJSONを保存・復元できます")
            
            # 1. EXPORT
            current_data = st.session_state['patient_db'].get(current_patient_id, [])
            json_str = json.dumps(current_data, indent=2, ensure_ascii=False)
            
            st.download_button(
                label="📤 DOWNLOAD JSON FILE",
                data=json_str,
                file_name=f"ICU_DATA_{current_patient_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json"
            )
            
            st.divider()
            st.caption("👇 過去のデータを復元 (Select File & Click Restore)")

            # 2. IMPORT (st.formによるループ防止)
            with st.form("json_restore_form", clear_on_submit=True):
                uploaded_file = st.file_uploader("📂 UPLOAD JSON FILE", type=['json'])
                submitted = st.form_submit_button("🔄 EXECUTE FILE RESTORE")

                if submitted and uploaded_file is not None:
                    try:
                        data = json.load(uploaded_file)
                        st.session_state['patient_db'][current_patient_id] = data
                        st.success(f"✅ FILE LOADED: {len(data)} records")
                        st.rerun()
                    except Exception as e:
                        st.error(f"File Error: {e}")
        # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

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

# === TAB 2: トレンド管理 (Zero-Filter Logic Implemented) ===
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
    ecmo_flow = c3.number_input("ECMO Flow (L/min)", step=0.1, help="VV-ECMO流量")

    # 電解質
    e1, e2, e3, e4 = st.columns(4)
    na = e1.number_input("Na", step=1.0)
    cl = e2.number_input("Cl", step=1.0)
    hco3 = e3.number_input("HCO3", step=0.1)
    alb = e4.number_input("Alb", step=0.1)

    # 計算ロジック
    pf, do2, vo2, o2er, ag, c_ag, flow_ratio = None, None, None, None, None, None, None
    
    if pao2 and fio2 and fio2>0:
        pf = pao2 / (fio2/100)
    
    if hb and co and spo2 and pao2:
        cao2 = 1.34*hb*(spo2/100) + 0.0031*pao2
        do2 = co*cao2*10
        if svo2:
            cvo2 = 1.34*hb*(svo2/100) + 0.0031*40
            vo2 = co*(cao2-cvo2)*10
            if do2 and do2>0:
                o2er = (vo2/do2)*100
    
    if na and cl and hco3:
        ag = na - (cl + hco3)
        if alb:
            c_ag = ag + 2.5 * (4.0 - alb)
    
    if co and ecmo_flow and co > 0:
        flow_ratio = (ecmo_flow / co) * 100

    # プレビュー
    if pf or do2 or o2er or ag:
        st.markdown("---")
        cols = st.columns(5)
        cols[0].metric("P/F", f"{pf:.0f}" if pf else "-")
        cols[1].metric("DO2", f"{do2:.0f}" if do2 else "-")
        cols[2].metric("VO2", f"{vo2:.0f}" if vo2 else "-")
        cols[3].metric("O2ER", f"{o2er:.1f}%" if o2er else "-")
        cols[4].metric("AG(c)", f"{c_ag:.1f}" if c_ag else (f"{ag:.1f}" if ag else "-"))
        
        if flow_ratio:
            ratio_label = "Flow/CO Ratio"
            ratio_val = f"{flow_ratio:.0f}%"
            ratio_delta = "Capture OK" if flow_ratio >= 60 else "⚠️ High Shunt"
            delta_color = "normal" if flow_ratio >= 60 else "inverse"
            st.metric(ratio_label, ratio_val, ratio_delta, delta_color=delta_color)

    # ▼▼▼▼▼▼ ZERO-FILTER LOGIC (V4.6 Logic) ▼▼▼▼▼▼
    if st.button("💾 SAVE DATA (Add to Session)"):
        if current_patient_id not in st.session_state['patient_db']: 
            st.session_state['patient_db'][current_patient_id] = []
        
        # 0 より大きい場合のみ値を保存、そうでなければ None
        record = {
            "Time": datetime.now().strftime("%H:%M:%S"),
            "P/F": pf if pf else None,
            "DO2": do2 if do2 else None,
            "VO2": vo2 if vo2 else None,
            "O2ER": o2er if o2er else None,
            "Lactate": lac if lac and lac > 0 else None,
            "Hb": hb if hb and hb > 0 else None,
            "pH": ph if ph and ph > 0 else None,
            "SvO2": svo2 if svo2 and svo2 > 0 else None,
            "AG": c_ag if c_ag else ag if ag else None,
            "Na": na if na and na > 0 else None,
            "Cl": cl if cl and cl > 0 else None,
            "HCO3": hco3 if hco3 and hco3 > 0 else None,
            "Alb": alb if alb and alb > 0 else None,
            "CO": co if co and co > 0 else None,
            "SpO2": spo2 if spo2 and spo2 > 0 else None,
            "PaO2": pao2 if pao2 and pao2 > 0 else None,
            "FiO2": fio2 if fio2 and fio2 > 0 else None,
            "ECMO_Flow": ecmo_flow if ecmo_flow and ecmo_flow > 0 else None,
            "Flow_Ratio": flow_ratio if flow_ratio else None
        }
        st.session_state['patient_db'][current_patient_id].append(record)
        st.rerun()
    
    # --- グラフ描画 (Dual Panel - Robust) ---
    hist = st.session_state['patient_db'].get(current_patient_id, [])
    if hist:
        df = pd.DataFrame(hist)
        
        all_possible_cols = [
            "P/F", "DO2", "VO2", "O2ER", "Lactate", "Hb", "pH", "SvO2", "AG",
            "Na", "Cl", "HCO3", "Alb", "CO", "SpO2", "PaO2", "FiO2",
            "ECMO_Flow", "Flow_Ratio"
        ]
        
        # 数値変換 & 欠損カラム補完
        for col in all_possible_cols:
            if col not in df.columns: df[col] = None
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        st.markdown("### 📉 DUAL TREND ANALYSIS")
        
        g1, g2 = st.columns(2)
        
        with g1:
            st.markdown("##### 📉 Trend Monitor A (Main)")
            wanted_vol = ["DO2", "VO2"]
            available_vol = [c for c in all_possible_cols if df[c].notna().any()] 
            safe_default_vol = list(set(wanted_vol).intersection(available_vol))
            
            selected_vol = st.multiselect(
                "Select Parameters A", options=available_vol, default=safe_default_vol, key="vol_sel"
            )
            if selected_vol:
                st.line_chart(df.set_index("Time")[selected_vol])
        
        with g2:
            st.markdown("##### 📉 Trend Monitor B (Sub/Correlated)")
            wanted_res = ["Lactate", "O2ER", "SvO2"]
            available_res = [c for c in all_possible_cols if df[c].notna().any()]
            safe_default_res = list(set(wanted_res).intersection(available_res))
            
            selected_res = st.multiselect(
                "Select Parameters B", options=available_res, default=safe_default_res, key="res_sel"
            )
            if selected_res:
                st.line_chart(df.set_index("Time")[selected_res])

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
            
            # 1. Search (V2.7 Logic - PROMISE KEPT)
            search_context = ""
            try:
                model_kw = genai.GenerativeModel(model_name=selected_model_name)
                # 👇 V2.7 Original Logic
                kw_prompt = f"Extract 3 medical keywords (space separated) for ICU patient search:\n{hist_text[:200]}\n{lab_text[:200]}"
                kw_res = model_kw.generate_content(kw_prompt)
                search_key = kw_res.text.strip()
                
                with st.spinner(f"🌐 Searching Evidence: {search_key}..."):
                    with DDGS() as ddgs:
                        # 👇 V2.7 Original Logic
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

                # ▼▼▼▼▼▼ 安全装置（Disclaimer） ▼▼▼▼▼▼
                st.markdown("---")
                st.warning("⚠️ **【重要】本システムは診断支援AIです。最終的な医療判断は必ず医師が行ってください。**")
                # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

            except Exception as e: st.error(f"System Error: {e}")
