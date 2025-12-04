import streamlit as st
import google.generativeai as genai
import pandas as pd
import re
from datetime import datetime

# ==========================================
# 0. アプリ設定 & スタイル
# ==========================================
COMPANY_NAME = "K's tech works. (K&G solution)"
APP_TITLE = "Super Critical Care Support System"

st.set_page_config(page_title=APP_TITLE, layout="wide", page_icon="🏥")

st.markdown(f"""
    <style>
    .footer {{
        position: fixed; left: 0; bottom: 0; width: 100%;
        background-color: #0E1117; color: #FAFAFA;
        text-align: center; padding: 10px; font-weight: bold;
        border-top: 1px solid #444; z-index: 100; font-family: sans-serif;
    }}
    .block-container {{ padding-bottom: 80px; }}
    </style>
    <div class="footer">Produced by {COMPANY_NAME}</div>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 草野次長の脳 (Google Search Ver.)
# ==========================================
KUSANO_BRAIN = """
あなたは、市立長浜病院・臨床工学技術科の次長であり、30年の臨床経験を持つ「草野（Kusano）」です。
これまでは厳しい指導を行ってきましたが、今回は**「極めて紳士的かつ論理的な臨床のプロフェッショナル」**として振る舞ってください。

あなたの役割は、提供された【生理学データ】と【Google検索による最新エビデンス】に基づき、客観的なアセスメントを行うことです。

【行動指針】
1. **情報収集**: ユーザーからの質問に対し、必要に応じて**Google検索ツール**を積極的に使用し、最新のガイドラインや医学論文の知見を参照してください。
2. **多角的クロスチェック**:
   - 単一の数値だけでなく、パラメータ間の相互作用（矛盾）を必ず評価してください。
   - 例: 「Hb低値時のO2ER正常（見かけ上の正常）」や「pH正常時のPaCO2/HCO3異常（代償機転）」は見逃さないこと。
3. **回答フォーマット**:
   - **総合評価**: 正常 / 注意 / 危険 （一言で）
   - **詳細分析**: パラメータごとの評価と、その根拠。
   - **臨床工学的アドバイス**: 現状から推奨されるアクション。
"""

# ==========================================
# 2. 関数群 (DB & Session)
# ==========================================
if 'patient_db' not in st.session_state:
    st.session_state['patient_db'] = {}

# ==========================================
# 3. サイドバー設定
# ==========================================
current_patient_id = None 

with st.sidebar:
    st.title("⚙️ System Config")
    api_key = st.text_input("Gemini API Key", type="password")
    
    # モデル選択
    selected_model_name = "gemini-1.5-pro"
    if api_key:
        genai.configure(api_key=api_key)
        try:
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            pro_models = [m for m in models if '1.5-pro' in m]
            if pro_models:
                selected_model_name = st.selectbox("AI Model", models, index=models.index(pro_models[0]))
            else:
                selected_model_name = st.selectbox("AI Model", models)
        except: pass

    st.markdown("---")
    
    # 患者ID入力 (セキュリティ: 半角英数のみ)
    patient_id_input = st.text_input(
        "🆔 患者ID (半角英数のみ)", 
        value="TEST1", 
        max_chars=10,
        help="個人情報保護のため、日本語（漢字・かな）は禁止です。イニシャルかID番号を使用してください。"
    )
    
    if patient_id_input:
        if not re.match(r'^[a-zA-Z0-9]+$', patient_id_input):
            st.error("⚠️ エラー: 半角英数字のみ使用可能です。")
            current_patient_id = None
        else:
            current_patient_id = patient_id_input.upper()
            st.success(f"Login: {current_patient_id}")
    else:
        st.warning("⚠️ IDを入力してください")
        current_patient_id = None
        
    st.markdown("---")
    
    if current_patient_id:
        if st.button("🗑️ 現在のIDのデータを消去"):
            st.session_state['patient_db'][current_patient_id] = []
            st.rerun()

# ==========================================
# 4. メインUI & 計算ロジック
# ==========================================
st.title(f"🏥 {APP_TITLE}")
st.caption(f"Advanced Clinical Engineering Support | Powered by {COMPANY_NAME}")

if current_patient_id is None:
    st.error("👈 サイドバーで正しい形式の【患者ID】を入力してください。")
    st.stop()

# --- 入力フォーム ---
st.info(f"💡 ID: **{current_patient_id}** のデータを入力中。")

col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("🫁 呼吸 (Resp)")
    pao2 = st.number_input("PaO2 (mmHg)", value=None, step=1.0)
    paco2 = st.number_input("PaCO2 (mmHg)", value=None, step=1.0)
    fio2_percent = st.number_input("FiO2 (%)", value=None, step=1.0)
    spo2 = st.number_input("SpO2 (%)", value=None, step=1.0)
with col2:
    st.subheader("💓 循環 (Circ)")
    hb = st.number_input("Hb (g/dL)", value=None, step=0.1)
    co = st.number_input("CO (L/min)", value=None, step=0.1)
    svo2 = st.number_input("SvO2/ScvO2 (%)", value=None, step=1.0)
    sbp = st.number_input("SBP", value=None, step=1)
    dbp = st.number_input("DBP", value=None, step=1)
with col3:
    st.subheader("🧪 代謝 (Metab)")
    ph = st.number_input("pH", value=None, step=0.01, format="%.2f")
    lac = st.number_input("Lactate", value=None, step=0.1)
    hco3 = st.number_input("HCO3-", value=None, step=0.1)
    na = st.number_input("Na", value=None, step=1)
    cl = st.number_input("Cl", value=None, step=1)
    alb = st.number_input("Alb", value=None, step=0.1)

# --- Python計算エンジン ---
pf_val = None; do2_val = None; vo2_val = None; o2er_val = None; ag_val = None
pf_msg = "ー"; do2_msg = "ー"; vo2_msg = "ー"; o2er_msg = "ー"; ag_msg = "ー"

if pao2 is not None and fio2_percent is not None and fio2_percent > 0:
    pf_val = pao2 / (fio2_percent / 100.0)
    pf_msg = f"{pf_val:.0f}"

if hb is not None and co is not None and spo2 is not None and pao2 is not None:
    sa_o2 = spo2 / 100.0
    cao2 = (1.34 * hb * sa_o2) + (0.0031 * pao2)
    do2_val = co * cao2 * 10
    do2_msg = f"{do2_val:.0f}"
    
    if svo2 is not None:
        sv_o2 = svo2 / 100.0
        cvo2 = (1.34 * hb * sv_o2) + (0.0031 * 40)
        vo2_val = co * (cao2 - cvo2) * 10
        vo2_msg = f"{vo2_val:.0f}"
        if do2_val > 0:
            o2er_val = (vo2_val / do2_val) * 100
            o2er_msg = f"{o2er_val:.1f}%"

if na is not None and cl is not None and hco3 is not None:
    ag_val = na - (cl + hco3)
    if alb is not None:
        ag_val = ag_val + 2.5 * (4.0 - alb)
    ag_msg = f"{ag_val:.1f}"

# --- 計算結果表示 ---
st.markdown("### 📊 Calculated Parameters")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("P/F Ratio", pf_msg)
m2.metric("DO2", do2_msg)
m3.metric("VO2", vo2_msg)
m4.metric("O2ER", o2er_msg)
m5.metric("Anion Gap", ag_msg)

# ==========================================
# 5. トレンド記録
# ==========================================
if current_patient_id not in st.session_state['patient_db']:
    st.session_state['patient_db'][current_patient_id] = []

current_history = st.session_state['patient_db'][current_patient_id]

if st.button("💾 データを記録 (Trend)"):
    record = {
        "Time": datetime.now().strftime("%H:%M:%S"),
        "P/F": pf_val if pf_val else 0,
        "DO2": do2_val if do2_val else 0,
        "O2ER": o2er_val if o2er_val else 0,
        "Lactate": lac if lac else 0,
        "pH": ph if ph else 7.4
    }
    st.session_state['patient_db'][current_patient_id].append(record)
    st.rerun()

if len(current_history) > 0:
    st.markdown(f"### 📈 Trend View (Patient: {current_patient_id})")
    df = pd.DataFrame(current_history)
    t1, t2 = st.columns(2)
    with t1:
        st.caption("呼吸・代謝 (P/F, O2ER, Lac)")
        st.line_chart(df.set_index("Time")[["P/F", "O2ER", "Lactate"]])
    with t2:
        st.caption("酸素供給 (DO2)")
        st.line_chart(df.set_index("Time")[["DO2"]])

# ==========================================
# 6. AI解析 (Google Search Only)
# ==========================================
st.markdown("---")
question = st.text_area("👨‍⚕️ 草野次長への相談", placeholder="例: 昇圧剤使用中ですが、循環動態の評価と推奨されるガイドラインを教えて。")

if st.button("🔍 解析開始 (With Google Search)", type="primary"):
    if not api_key:
        st.error("APIキーを入力してください。")
    else:
        physio_text = f"""
        【現在データ】
        [呼吸] P/F:{pf_msg}, PaO2:{pao2}, PaCO2:{paco2}
        [循環] DO2:{do2_msg}, VO2:{vo2_msg}, O2ER:{o2er_msg}, Hb:{hb}, CO:{co}
        [代謝] pH:{ph}, Lac:{lac}, AG:{ag_msg}, HCO3:{hco3}
        [血圧] {sbp}/{dbp}
        """

        user_prompt = f"""
        以下の臨床データを評価してください。
        {physio_text}
        【相談内容】
        {question}
        """

        # Google Search Tool ON
        tools = [{"google_search": {}}]
        
        try:
            model = genai.GenerativeModel(
                model_name=selected_model_name,
                tools=tools,
                generation_config={"temperature": 0.0},
                system_instruction=KUSANO_BRAIN
            )
            
            with st.spinner("草野次長がWeb検索中... (Searching...)"):
                response = model.generate_content(user_prompt)
                
            st.markdown("### 👨‍⚕️ Analysis Result")
            st.write(response.text)
            
            if response.candidates[0].grounding_metadata.search_entry_point:
                st.caption("🌐 参照ソース (Google Search)")
                st.write(response.candidates[0].grounding_metadata.search_entry_point.rendered_content)

        except Exception as e:
            st.error(f"Error: {e}")
