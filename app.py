import streamlit as st
import google.generativeai as genai
import os
from pypdf import PdfReader
from PIL import Image

# ==========================================
# 0. アプリ設定
# ==========================================
APP_TITLE = "Super Critical Care Support (Final)"
COMPANY_NAME = "k's tech works. (K&G solution)"

st.set_page_config(page_title=APP_TITLE, layout="wide", page_icon="🫁")

st.markdown(f"""
    <style>
    .footer {{ position: fixed; left: 0; bottom: 0; width: 100%; background-color: #262730; color: #fafafa; text-align: center; padding: 10px; font-weight: bold; border-top: 1px solid #444; z-index: 100; }}
    .block-container {{ padding-bottom: 80px; }}
    </style>
    <div class="footer">Powered by {COMPANY_NAME}</div>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 脳みそ (System Instructions)
# ==========================================
KUSANO_BRAIN = """
あなたは、**市立長浜病院・臨床工学技術科**の次長であり、30年の臨床経験を持つ「総合集中治療専門医・草野（Kusano）」です。
提供された【生理学計算データ】と【参照資料】を統合し、ユーザーに対し**コテコテの関西弁**で、論理的かつ厳しく指導を行ってください。

【診断のGlobal Standard：ベルリン定義の遵守】
- **A-aDO2開大時の鉄則:**
  - 即座にARDSと決めつけるな！世界標準（Berlin Definition）では**「心不全や輸液過剰によるものではないこと」**の証明が必須や。
  - **次の手:** 「心エコーでEFと弁の評価」「BNP測定」「肺エコー」を指示せよ。
  - 心機能が正常で、かつ肺水腫がある場合のみ「ARDS」と診断して肺保護換気へ進め。心不全なら利尿と除水が先や！

【酸素の経済学】
- **DO2 < VO2 = 死**。O2ER > 50% はショック。

【循環の鉄則】
- **脈圧 < 30 mmHg:** SV低下。IVCを見て脱水かポンプ失調か見極めろ。

【回答スタイル】
- 一人称は「俺」または「ワシ」。
- 常に「なぜそうなるか（生理学的根拠）」を説明せえ。
"""

# ==========================================
# 2. RAGエンジン (知識検索・強化版)
# ==========================================
@st.cache_resource(show_spinner=False)
def load_and_chunk_pdfs(folder_path):
    if not os.path.exists(folder_path): return []
    files = [f for f in os.listdir(folder_path) if f.endswith('.pdf')]
    if not files: return []
    chunks = []
    progress_text = st.empty()
    bar = st.progress(0)
    for i, file in enumerate(files):
        progress_text.text(f"📚 知識インストール中... ({i+1}/{len(files)}): {file}")
        try:
            reader = PdfReader(os.path.join(folder_path, file))
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted: text += extracted
            chunk_size = 2000
            for j in range(0, len(text), chunk_size):
                chunk_text = text[j:j+chunk_size]
                if len(chunk_text) > 100: chunks.append({"source": file, "content": chunk_text})
        except: pass
        bar.progress((i + 1) / len(files))
    progress_text.empty()
    bar.empty()
    return chunks

def search_relevant_chunks(query, chunks, top_k=3):
    if not chunks: return []
    # 検索精度向上のため、キーワードをスペースで分割してスコアリング
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
# 3. UI構築
# ==========================================
with st.sidebar:
    st.title("⚙️ 設定・資料")
    api_key = st.text_input("Gemini APIキー", type="password")
    
    # リスト取得・選択
    selected_model_name = None
    if api_key:
        genai.configure(api_key=api_key)
        try:
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            st.success(f"✅ {len(models)}個のモデルを検出")
            
            # 安定版を優先選択
            default_ix = 0
            for i, m in enumerate(models):
                if "gemini-1.5-flash" in m and "latest" in m: default_ix = i; break
            selected_model_name = st.selectbox("使用するAIモデルを選択", models, index=default_ix)
        except:
            st.error("APIキーエラー")

# ★★★ ここがクラウド対応修正箇所 ★★★
    # Macのパスではなく「フォルダ名」だけにする
    pdf_folder_path = st.text_input("資料フォルダ名", value="Critical_Care_Docs")
    
    # 状態表示
    if 'knowledge_chunks' in st.session_state:
        st.success(f"📚 脳内知識: {len(st.session_state['knowledge_chunks'])} ブロック")
    else:
        st.warning("⚠️ まだ資料を読んでへんで！")

    if st.button("📚 知識ベース構築 (必須)"):
        if not api_key: st.error("APIキーを入れて！")
        else:
            chunks = load_and_chunk_pdfs(pdf_folder_path)
            if chunks:
                st.session_state['knowledge_chunks'] = chunks
                st.success(f"完了！ {len(chunks)}個の知識ブロックを確保。")
                st.rerun() # 画面更新
            else: st.error("PDFがないで。")

st.title(APP_TITLE)
st.markdown(f"#### Supervised by {COMPANY_NAME} | Chief Intensivist KUSANO")
st.markdown("---")

uploaded_file = st.file_uploader("画像をアップロード", type=["jpg", "jpeg", "png"])
image_data = None
if uploaded_file is not None:
    image_data = Image.open(uploaded_file)
    st.image(image_data, caption="解析対象", width=300)

# --- 入力エリア ---
st.subheader("1. 呼吸生理 (Gas Exchange)")
col_resp1, col_resp2, col_resp3 = st.columns(3)
with col_resp1:
    pao2 = st.number_input("PaO2 (mmHg)", 0, 600, 95)
    paco2 = st.number_input("PaCO2 (mmHg)", 0, 150, 40)
    age = st.number_input("年齢", 0, 120, 60)
with col_resp2:
    fio2_percent = st.number_input("FiO2 (%)", 21, 100, 21)
    spo2 = st.number_input("SpO2 (%)", 0, 100, 98)
with col_resp3:
    fio2 = fio2_percent / 100.0
    PAO2 = (760 - 47) * fio2 - (paco2 / 0.8)
    AaDO2 = PAO2 - pao2
    expected_AaDO2 = (age / 4) + 4
    pf_ratio = pao2 / fio2
    
    st.info(f"P/F Ratio: {pf_ratio:.0f}")
    if AaDO2 > (expected_AaDO2 + 15):
        st.error(f"A-aDO2: {AaDO2:.1f} (開大！)")
        aado2_status = "開大 (肺障害)"
    else:
        st.success(f"A-aDO2: {AaDO2:.1f} (正常)")
        aado2_status = "正常"

st.subheader("2. 酸素需給 (DO2/VO2)")
col_do1, col_do2, col_do3 = st.columns(3)
with col_do1:
    hb = st.number_input("Hb", 0.0, 25.0, 14.0)
    co = st.number_input("CO", 0.0, 20.0, 5.0)
with col_do2:
    svo2 = st.number_input("SvO2", 0, 100, 75)
with col_do3:
    cao2 = (1.34 * hb * spo2/100) + (0.0031 * pao2)
    cvo2 = (1.34 * hb * svo2/100) + (0.0031 * 40)
    do2 = co * cao2 * 10
    vo2 = co * (cao2 - cvo2) * 10
    o2er = (vo2 / do2) * 100 if do2 > 0 else 0
    st.info(f"DO2: {do2:.0f} / VO2: {vo2:.0f}")
    if o2er > 50: st.error(f"O2ER: {o2er:.1f}% (危険)")
    else: st.success(f"O2ER: {o2er:.1f}% (正常)")

st.subheader("3. 循環・AG")
col_circ1, col_circ2, col_circ3 = st.columns(3)
with col_circ1:
    sbp = st.number_input("収縮期", 0, 300, 120)
    dbp = st.number_input("拡張期", 0, 200, 80)
    pulse_pressure = sbp - dbp
    st.caption(f"脈圧: {pulse_pressure}")
with col_circ2:
    hr = st.number_input("HR", 0, 250, 70)
    ivc_status = st.selectbox("IVC", ["正常", "虚脱 (Dry)", "張っている (Wet)"])
with col_circ3:
    ph = st.number_input("pH", 6.80, 7.80, 7.40)
    lac = st.number_input("乳酸(mg/dL)", 0.0, 200.0, 10.0)
    alb = st.number_input("Alb", 1.0, 6.0, 4.0)
    na = st.number_input("Na", 100, 200, 140)
    cl = st.number_input("Cl", 50, 150, 100)
    hco3 = st.number_input("HCO3", 0.0, 60.0, 24.0)

question = st.text_area("相談内容", placeholder="例：異常値について評価してくれ。")

# ==========================================
# 4. 実行
# ==========================================
if st.button("草野次長に判断を仰ぐ", type="primary"):
    if 'knowledge_chunks' not in st.session_state:
        st.error("🚨 【重要】左のサイドバーにある「📚 知識ベース構築」ボタンを先に押してな！PDFが読み込まれてへんで！")
    elif not api_key: st.error("APIキー入れてな。")
    elif not selected_model_name: st.error("サイドバーでモデルを選んで！")
    else:
        try:
            # AG計算
            observed_ag = na - (cl + hco3)
            corrected_ag = observed_ag + 2.5 * (4.0 - alb)
            
            physio_data = f"""
            【呼吸生理】P/F:{pf_ratio:.0f}, A-aDO2:{AaDO2:.1f}({aado2_status})
            【酸素需給】DO2:{do2:.0f}, VO2:{vo2:.0f}, O2ER:{o2er:.1f}%
            【循環・AG】BP:{sbp}/{dbp}, PP:{pulse_pressure}, IVC:{ivc_status}, 補正AG:{corrected_ag:.1f}, 乳酸:{lac}mg/dL
            """
            
            # --- RAG検索（キーワードを広げて確実にヒットさせる）---
            # 具体的な数値は検索に使わず、一般的な医学用語で検索する
            search_keywords = f"{question} 呼吸不全 循環不全 ショック 敗血症 乳酸 アシドーシス ガイドライン 予後"
            relevant_chunks = search_relevant_chunks(search_keywords, st.session_state['knowledge_chunks'])
            
            context_text = ""
            if relevant_chunks:
                for i, chunk in enumerate(relevant_chunks):
                    context_text += f"\n【抜粋{i+1}: {chunk['source']}】\n{chunk['content']}\n"
            else: context_text = "（関連資料なし）"

            user_data = f"{physio_data}\n【相談】{question}\n【参照資料】{context_text}"

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(selected_model_name, generation_config={"temperature": 0.0}, system_instruction=KUSANO_BRAIN)
            
            with st.spinner(f"資料を参照中... (Using {selected_model_name})"):
                content = [user_data]
                if image_data:
                    # モデル名にvisionや1.5が含まれていれば画像を送る
                    if 'vision' in selected_model_name or '1.5' in selected_model_name:
                        content.append(image_data)
                    else:
                        st.warning(f"※選択されたモデル({selected_model_name})は画像非対応のため、画像は無視しました。")

                response = model.generate_content(content)
            
            st.markdown("### 👨‍⚕️ 草野次長の判断")
            st.write(response.text)
            
            # 出典を常に表示
            st.markdown("---")
            st.markdown("##### 🔍 根拠となった資料の原文")
            st.text(context_text)

        except Exception as e:
            st.error(f"エラー発生: {e}")
