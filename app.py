import streamlit as st
import google.generativeai as genai
import os
import pandas as pd
import re
from datetime import datetime
from pypdf import PdfReader

# ==========================================
# 0. アプリ設定 & スタイル
# ==========================================
COMPANY_NAME = "K's tech works. (K&G solution)"
APP_TITLE = "Super Critical Care Support System"

st.set_page_config(page_title=APP_TITLE, layout="wide", page_icon="🏥")

# フッターとスタイルの定義
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
# 1. 草野次長の脳 (System Instruction)
# ==========================================
KUSANO_BRAIN = """
あなたは、市立長浜病院・臨床工学技術科の次長であり、30年の臨床経験を持つ「草野（Kusano）」です。
これまでは厳しい指導を行ってきましたが、今回は**「極めて紳士的かつ論理的な臨床のプロフェッショナル」**として振る舞ってください。

あなたの役割は、提供された【生理学データ】と、RAG/Web検索による【参照資料】に基づき、客観的なアセスメントを行うことです。

【行動指針】
1. **情報の優先順位**:
   - **最優先**: 提供された【参照資料（PDF）】。院内の規定や手持ちの文献を「正」とします。
   - **次点**: 資料に記載がない場合、**Google検索機能を使用して**、信頼できる医学的ソース（ガイドライン、論文要旨）を検索し、その情報を補完してください。

2. **多角的視点によるクロスチェック**:
   - 単一の数値だけでなく、パラメータ間の相互作用（矛盾）を必ず評価してください。
   - **重要**: 「Hb低値時のO2ER正常（見かけ上の正常）」や「pH正常時のPaCO2/HCO3異常（代償機転）」は見逃さないこと。

3. **回答フォーマット**:
   - **総合評価**: 正常 / 注意 / 危険 （一言で）
   - **詳細分析**: パラメータごとの評価と、その根拠（出典）。
   - **臨床工学的アドバイス**: 現状から推奨されるアクション。

4. **ハルシネーション防止**:
   - PDFに基づく情報か、Google検索に基づく情報か、出典を明確に区別して答えてください。
"""

# ==========================================
# 2. 関数群 (RAG & DB)
# ==========================================
# 患者データベースの初期化
if 'patient_db' not in st.session_state:
    st.session_state['patient_db'] = {}

@st.cache_resource(show_spinner=False)
def load_and_chunk_pdfs(folder_path):
    if not os.path.exists(folder_path): return []
    files = [f for f in os.listdir(folder_path) if f.endswith('.pdf')]
    if not files: return []
    chunks = []
    
    status_bar = st.progress(0)
    for i, file in enumerate(files):
        try:
            reader = PdfReader(os.path.join(folder_path, file))
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted: text += extracted
            
            chunk_size = 3000
            for j in range(0, len(text), chunk_size):
                chunk_text = text[j:j+chunk_size]
                if len(chunk_text) > 100:
                    chunks.append({"source": file, "content": chunk_text})
        except: pass
        status_bar.progress((i + 1) / len(files))
    status_bar.empty()
    return chunks

def search_relevant_chunks(query, chunks, top_k=5):
    if not chunks: return []
    keywords = query.replace("　", " ").split()
    scored_chunks = []
    for chunk in chunks:
        score = 0
        for k in keywords:
            if k in chunk["content"]: score += 1
        if score > 0: scored_chunks.append((score, chunk))
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored_chunks[:top_k]]

# ==========================================
# 3. サイドバー設定 (セキュリティ強化版)
# ==========================================
current_patient_id = None # グローバル変数として初期化

with st.sidebar:
    st.title("⚙️ System Config")
    api_key = st.text_input("Gemini API Key", type="password")
    
    # モデル選択 (Pro推奨)
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
    
    # --- 患者ID (セキュリティ検証) ---
    patient_id_input = st.text_input(
        "🆔 患者ID (半角英数のみ)", 
        value="TEST1", 
        max_chars=10,
        help="個人情報保護のため、日本語（漢字・かな）は禁止です。イニシャルかID番号を使用してください。"
    )
    
    if patient_id_input:
        # 正規表現: 英数字のみ許可
        if not re.match(r'^[a-zA-Z0-9]+$', patient_id_input):
            st.error("⚠️ エラー: 半角英数字のみ使用可能です。\n（漢字・ひらがなは入力禁止）")
            current_patient_id = None
        else:
            current_patient_id = patient_id_input.upper() # 自動で大文字統一
            st.success(f"Login: {current_patient_id}")
    else:
        st.warning("⚠️ IDを入力してください")
        current_patient_id = None
        
    st.markdown("---")
    
    # 履歴消去ボタン (現在のIDのみ)
    if current_patient_id:
        if st.button("🗑️ 現在のIDのデータを消去"):
            st.session_state['patient_db'][current_patient_id] = []
            st.rerun()

    # PDF設定
    pdf_folder_path = st.text_input("資料フォルダ (Path)", value="Critical_Care_Docs")
    if st.button("📚 知識ベース再構築"):
        chunks = load_and_chunk_pdfs(pdf_folder_path)
        if chunks:
            st.session_state['knowledge_chunks'] = chunks
            st.success(f"完了: {len(chunks)} Chunks")
        else:
            st.error("PDFが見つかりません")

# ==========================================
# 4. メインUI & 計算ロジック
# ==========================================
st.title(f"🏥 {APP_TITLE}")
st.caption(f"Advanced Clinical Engineering Support | Powered by {COMPANY_NAME}")

if current_patient_id is None:
    st.error("👈 サイドバーで正しい形式の【患者ID】を入力してください。機能がロックされています。")
    st.stop() # IDがない場合はここで処理を止める

# --- 入力フォーム ---
st.info(f"💡 ID: **{current_patient_id}** のデータを入力中。空欄は「不明」として扱います。")

col1, col2, col3 = st.columns(3)

# 1. 呼吸
with col1:
    st.subheader("🫁 呼吸 (Resp)")
    pao2 = st.number_input("PaO2 (mmHg)", value=None, step=1.0)
    paco2 = st.number_input("PaCO2 (mmHg)", value=None, step=1.0)
    fio2_percent = st.number_input("FiO2 (%)", value=None, step=1.0)
    spo2 = st.number_input("SpO2 (%)", value=None, step=1.0)

# 2. 循環・酸素
with col2:
    st.subheader("💓 循環 (Circ)")
    hb = st.number_input("Hb (g/dL)", value=None, step=0.1)
    co = st.number_input("CO (L/min)", value=None, step=0.1)
    svo2 = st.number_input("SvO2/ScvO2 (%)", value=None, step=1.0)
    sbp = st.number_input("收縮期BP", value=None, step=1)
    dbp = st.number_input("拡張期BP", value=None, step=1)

# 3. 代謝・酸塩基
with col3:
    st.subheader("🧪 代謝 (Metab)")
    ph = st.number_input("pH", value=None, step=0.01, format="%.2f")
    lac = st.number_input("Lactate (mg/dL)", value=None, step=0.1)
    hco3 = st.number_input("HCO3-", value=None, step=0.1)
    na = st.number_input("Na", value=None, step=1)
    cl = st.number_input("Cl", value=None, step=1)
    alb = st.number_input("Alb", value=None, step=0.1)

# --- Python計算エンジン ---
pf_val = None; do2_val = None; vo2_val = None; o2er_val = None; ag_val = None
pf_msg = "ー"; aado2_msg = "ー"; do2_msg = "ー"; vo2_msg = "ー"; o2er_msg = "ー"; ag_msg = "ー"

if pao2 is not None and fio2_percent is not None and fio2_percent > 0:
    pf_val = pao2 / (fio2_percent / 100.0)
    pf_msg = f"{pf_val:.0f}"

if pao2 is not None and paco2 is not None and fio2_percent is not None:
    PAO2 = (760 - 47) * (fio2_percent/100) - (paco2 / 0.8)
    aado2_val = PAO2 - pao2
    aado2_msg = f"{aado2_val:.1f}"

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
# 5. トレンド記録 (患者ID別)
# ==========================================
# 現在のIDのDB箱を用意
if current_patient_id not in st.session_state['patient_db']:
    st.session_state['patient_db'][current_patient_id] = []

current_history = st.session_state['patient_db'][current_patient_id]

if st.button("💾 現在のデータを記録 (Add to Trend)"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    record = {
        "Time": timestamp,
        "P/F": pf_val if pf_val else 0,
        "DO2": do2_val if do2_val else 0,
        "O2ER": o2er_val if o2er_val else 0,
        "Lactate": lac if lac else 0,
        "pH": ph if ph else 7.4
    }
    st.session_state['patient_db'][current_patient_id].append(record)
    st.success(f"ID: {current_patient_id} にデータを追加しました。")
    st.rerun()

# グラフ表示
if len(current_history) > 0:
    st.markdown(f"### 📈 Trend View (Patient: {current_patient_id})")
    df = pd.DataFrame(current_history)
    
    t1, t2 = st.columns(2)
    with t1:
        st.caption("呼吸・代謝 (P/F, O2ER, Lactate)")
        st.line_chart(df.set_index("Time")[["P/F", "O2ER", "Lactate"]])
    with t2:
        st.caption("酸素供給 (DO2)")
        st.line_chart(df.set_index("Time")[["DO2"]])
else:
    st.info(f"ID: {current_patient_id} のトレンドデータはまだありません。")

# ==========================================
# 6. AI解析 (RAG + Google Search)
# ==========================================
st.markdown("---")
question = st.text_area("👨‍⚕️ 草野次長への相談 (Consultation)", placeholder="例: Hbが低いですが輸血適応について評価してください。")

if st.button("🔍 草野次長に解析を依頼 (Analysis)", type="primary"):
    if not api_key:
        st.error("APIキーを入力してください。")
    else:
        # データ整形
        physio_text = f"""
        【現在データ】
        [呼吸] P/F:{pf_msg}, PaO2:{pao2}, PaCO2:{paco2}
        [循環] DO2:{do2_msg}, VO2:{vo2_msg}, O2ER:{o2er_msg}, Hb:{hb}, CO:{co}
        [代謝] pH:{ph}, Lac:{lac}, AG:{ag_msg}, HCO3:{hco3}
        [血圧] {sbp}/{dbp}
        """

        # RAG検索
        context_text = "（手元の資料には関連情報なし）"
        if 'knowledge_chunks' in st.session_state:
            query = f"{question} {physio_text}"
            chunks = search_relevant_chunks(query, st.session_state['knowledge_chunks'])
            if chunks:
                context_text = "\n".join([f"【院内資料: {c['source']}】\n{c['content']}" for c in chunks])

        # プロンプト作成
        user_prompt = f"""
        以下の臨床データを評価してください。
        
        {physio_text}
        
        【相談内容】
        {question}
        
        【院内参照資料 (PDF Search Result)】
        {context_text}
        """

        # Google Search Tool設定
        tools = [{"google_search": {}}]
        
        try:
            model = genai.GenerativeModel(
                model_name=selected_model_name,
                tools=tools, # 👈 Google Search Grounding ON
                generation_config={"temperature": 0.0},
                system_instruction=KUSANO_BRAIN
            )
            
            with st.spinner("草野次長が思考中... (Searching Guidelines & Web)"):
                response = model.generate_content(user_prompt)
                
            st.markdown("### 👨‍⚕️ Analysis Result")
            st.write(response.text)
            
            # 参照元の表示 (Web検索を使用した場合)
            if response.candidates[0].grounding_metadata.search_entry_point:
                st.caption("🌐 Used Google Search Sources")
                st.write(response.candidates[0].grounding_metadata.search_entry_point.rendered_content)

        except Exception as e:
            st.error(f"Error: {e}")
