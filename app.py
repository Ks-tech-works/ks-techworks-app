import streamlit as st
import google.generativeai as genai
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
# 1. 脳みそ (情報ソース格付け機能搭載)
# ==========================================
KUSANO_BRAIN = """
あなたは、市立長浜病院・臨床工学技術科次長「草野（Kusano）」です。
提供された情報を統合し、論理的に診断推論を行ってください。

【絶対ルール：情報の格付け (Source Grading)】
Google検索機能を使用する際は、必ず情報の出所（ドメイン）を確認し、以下の基準で情報の信頼性を評価してください。

1. **推奨ソース (High Reliability)**:
   - 公的機関: `.go.jp`, `.gov` (厚労省、CDCなど)
   - 学術機関: `.ac.jp`, `.edu` (大学病院、研究機関)
   - 学会・公的団体: `.or.jp` (日本循環器学会、JSEPTICなど)
   - 信頼できる医学誌: `jstage`, `pubmed`, `nejm` など
   👉 これらの情報を最優先し、「推奨される」と判断して良い。

2. **非推奨・注意ソース (Low Reliability)**:
   - 個人のブログ、まとめサイト、Q&Aサイト、企業の広告記事
   👉 これらの情報は原則として除外するか、引用する場合は必ず「※信頼性が低い情報源ですが」と**注意書き**を付けること。

【回答フォーマット】
1. **Clinical Summary**: 患者の状態要約。
2. **Integrated Assessment**: 病歴と数値を統合した見解。
3. **Plan / Action**: 推奨されるアクション。
4. **Evidence & Grading**:
   - 参照したガイドラインや文献を挙げ、その後に必ず【信頼度: 高/低】を記載せよ。
   - 例: 「日本集中治療医学会 敗血症ガイドライン2020 (信頼度: 高)」
"""

# ==========================================
# 2. データ管理
# ==========================================
if 'patient_db' not in st.session_state:
    st.session_state['patient_db'] = {}

# ==========================================
# 3. サイドバー (ID管理)
# ==========================================
current_patient_id = None 

with st.sidebar:
    st.title("⚙️ System Config")
    
    # 1. SecretsからAPIキーを自動読み込み
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("🔑 API Key Loaded!")  # 読み込み成功マーク
    except:
        # 万が一設定し忘れた時用（またはローカル用）の手動入力
        api_key = st.text_input("Gemini API Key", type="password")
    
    selected_model_name = "gemini-1.5-pro"
    if api_key:
        genai.configure(api_key=api_key)
        try:
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            pro_models = [m for m in models if '1.5-pro' in m]
            if pro_models:
                selected_model_name = st.selectbox("AI Model", models, index=models.index(pro_models[0]))
        except: pass

    st.markdown("---")
    
    patient_id_input = st.text_input(
        "🆔 患者ID (半角英数のみ)", 
        value="TEST1", 
        max_chars=10,
        help="日本語禁止。イニシャルかID番号のみ。"
    )
    
    if patient_id_input:
        if not re.match(r'^[a-zA-Z0-9]+$', patient_id_input):
            st.error("⚠️ エラー: 半角英数字のみ使用可能です。")
            current_patient_id = None
        else:
            current_patient_id = patient_id_input.upper()
            st.success(f"Login: {current_patient_id}")
            
            st.markdown("---")
            if st.button("🗑️ このIDのデータを消去"):
                st.session_state['patient_db'][current_patient_id] = []
                st.rerun()
    else:
        st.warning("⚠️ IDを入力してください")
        current_patient_id = None

# ==========================================
# 4. メイン画面
# ==========================================
st.title(f"👨‍⚕️ {APP_TITLE}")

if current_patient_id is None:
    st.stop()

st.caption(f"Patient ID: **{current_patient_id}**")

tab1, tab2 = st.tabs(["📝 総合診断 (Crossover Analysis)", "📈 トレンド管理 (Trends)"])

# ------------------------------------------------
# TAB 2: トレンド管理 (グラフ修正版)
# ------------------------------------------------
with tab2:
    st.info("数値入力 (必要な項目のみ)")
    c1, c2, c3 = st.columns(3)
    pao2 = c1.number_input("PaO2", step=1.0, value=None, key="n_pao2")
    fio2 = c1.number_input("FiO2", step=1.0, value=None, key="n_fio2")
    lac = c1.number_input("Lactate", step=0.1, value=None, key="n_lac")
    hb = c2.number_input("Hb", step=0.1, value=None, key="n_hb")
    co = c2.number_input("CO", step=0.1, value=None, key="n_co")
    spo2 = c2.number_input("SpO2", step=1.0, value=None, key="n_spo2")
    ph = c3.number_input("pH", step=0.01, value=None, key="n_ph")
    svo2 = c3.number_input("SvO2", step=1.0, value=None, key="n_svo2")

    # 計算ロジック
    pf, do2, o2er = None, None, None
    if pao2 is not None and fio2 is not None and fio2 > 0:
        pf = pao2 / (fio2/100)
    if hb is not None and co is not None and spo2 is not None and pao2 is not None:
        cao2 = 1.34*hb*(spo2/100) + 0.0031*pao2
        do2 = co*cao2*10
        if svo2 is not None:
            cvo2 = 1.34*hb*(svo2/100) + 0.0031*40
            vo2 = co*(cao2-cvo2)*10
            if do2 is not None and do2 > 0:
                o2er = (vo2/do2)*100
    
    # プレビュー
    cols = st.columns(3)
    if pf is not None: cols[0].metric("P/F", f"{pf:.0f}")
    if do2 is not None: cols[1].metric("DO2", f"{do2:.0f}")
    if o2er is not None: cols[2].metric("O2ER", f"{o2er:.1f}%")

    # 記録ボタン
    if st.button("💾 記録"):
        if current_patient_id not in st.session_state['patient_db']: 
            st.session_state['patient_db'][current_patient_id] = []
        
        # タイムスタンプと共に保存
        st.session_state['patient_db'][current_patient_id].append({
            "Time": datetime.now().strftime("%H:%M:%S"),
            "P/F": pf, 
            "DO2": do2, 
            "O2ER": o2er,
            "Lactate": lac, # 乳酸もグラフ用に追加
            "Hb": hb        # Hbもグラフ用に追加
        })
        st.rerun()
    
    # グラフ描画（ここを修正しました！）
    hist = st.session_state['patient_db'].get(current_patient_id, [])
    if hist:
        df = pd.DataFrame(hist)
        
        # ★修正ポイント: 全てのデータを強制的に「数値」に変換する
        # これをやらないと、Noneが混じった時にグラフが壊れます
        numeric_cols = ["P/F", "DO2", "O2ER", "Lactate", "Hb"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        st.markdown("##### 呼吸・代謝 (P/F, O2ER, Lac)")
        st.line_chart(df.set_index("Time")[["P/F", "O2ER", "Lactate"]])
        
        st.markdown("##### 循環 (DO2, Hb)")
        st.line_chart(df.set_index("Time")[["DO2", "Hb"]])

# ------------------------------------------------
# TAB 1: 総合診断 (クロスオーバー機能搭載)
# ------------------------------------------------
with tab1:
    st.markdown("#### 💬 Multimodal Clinical Assessment")
    st.markdown("Tab2で記録された数値トレンドと、ここに入力する病歴情報を**統合して**解析します。")
    
    col_d1, col_d2 = st.columns([1, 1])
    with col_d1:
        history_text = st.text_area("病歴・主訴・現病歴", height=200, placeholder="例: 慢性腎不全で透析中。3日前から黒色便あり...")
        lab_text_paste = st.text_area("追加の検査データ (Labs Paste)", height=200, placeholder="WBC 12000, CRP 15.0...")
    with col_d2:
        uploaded_files = st.file_uploader("画像資料 (Drop Here)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
        if uploaded_files:
            st.image(uploaded_files, caption=[f.name for f in uploaded_files], width=150)

    st.markdown("---")
    if st.button("🔍 草野次長に統合診断を依頼", type="primary"):
        if not api_key:
            st.error("APIキーを入力してください。")
        else:
            # --- ここがクロスオーバーの核 ---
            # 1. Tab2のトレンドデータを取得
            trend_data_str = "（トレンドデータなし）"
            trend_history = st.session_state['patient_db'].get(current_patient_id, [])
            
            if trend_history:
                # 直近5件のデータを抽出して文字列化
                df_trend = pd.DataFrame(trend_history)
                recent_trend = df_trend.tail(5) 
                # AIが読みやすい形式に変換 (Markdown Table)
                trend_data_str = recent_trend.to_markdown(index=False)
            
            # 2. プロンプトに全情報を統合
            prompt_text = f"""
            以下の患者情報を【統合的に】分析してください。
            特に、Tab2のトレンドデータの変化が、Tab1の病歴（既往歴）で説明できるものか、新規の病態かを鑑別してください。

            【Tab 1: 病歴・背景情報】
            {history_text if history_text else "記載なし"}
            
            【Tab 1: 追加検査データ】
            {lab_text_paste if lab_text_paste else "記載なし"}

            【Tab 2: 時系列トレンドデータ (直近5点)】
            {trend_data_str}
            """
            
            user_content = [prompt_text]
            if uploaded_files:
                for f in uploaded_files:
                    img = Image.open(f)
                    user_content.append(img)
            
            tools = [{"google_search": {}}]
            try:
                model = genai.GenerativeModel(model_name=selected_model_name, tools=tools, system_instruction=KUSANO_BRAIN)
                with st.spinner("Tab1の病歴とTab2のトレンドを照合中..."):
                    response = model.generate_content(user_content)
                st.markdown("### 👨‍⚕️ Integrated Assessment Result")
                st.write(response.text)
                if response.candidates[0].grounding_metadata.search_entry_point:
                    st.caption("🌐 Referenced Sources")
                    st.write(response.candidates[0].grounding_metadata.search_entry_point.rendered_content)
            except Exception as e:
                st.error(f"Error: {e}")
