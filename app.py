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
# 1. 脳みそ (クロスオーバー分析対応)
# ==========================================
KUSANO_BRAIN = """
あなたは、市立長浜病院・臨床工学技術科次長であり、30年の経験を持つ「草野（Kusano）」です。
若手医師を指導する「熟練の臨床パートナー」として振る舞ってください。

【ミッション】
提供された「病歴・画像（Tab1）」と「時系列数値データ（Tab2）」を**クロスオーバー（統合）**させ、現在の病態を論理的に鑑別してください。

【思考プロセス】
1. **時系列トレンドの解釈**: Tab2のデータから、急激な変化（Acute）か、緩徐な変化（Chronic）かを見極めること。
   - 例: Hbの低下があっても、O2ERが安定しており、かつ既往に「腎不全」があれば腎性貧血の可能性を考慮する。
   - 例: 既往に関わらず、急激なDo2低下やLactate上昇があれば、緊急事態（出血、敗血症など）として警告する。
2. **コンテキストの結合**: 「数値の異常」が「既往歴」で説明つくものか、それとも「新規の合併症」なのかを評価する。
3. **検索活用**: 判断に迷う場合はGoogle検索ツールを使用しエビデンスを提示する。

【回答フォーマット】
1. **Clinical Summary**: 患者の状態要約（トレンド変化含む）。
2. **Integrated Assessment**: **病歴と数値を統合した見解**。
   - 「〇〇の数値傾向は、既往歴の△△と矛盾しませんが、念のため〜を疑います」といった記述。
3. **Differential Diagnosis**: 鑑別疾患リスト。
4. **Plan / Action**: 推奨されるアクション。
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
# TAB 2: トレンド管理 (先に計算ロジックを配置)
# ------------------------------------------------
with tab2:
    st.markdown("#### 📈 Vital & Physio Trends")
    st.info("💡 必要な項目だけ入力して記録してください。ここに入力されたデータはTab1の診断でも参照されます。")
    
    c_t1, c_t2, c_t3 = st.columns(3)
    with c_t1:
        pao2 = st.number_input("PaO2", step=1.0, value=None, key="n_pao2")
        fio2 = st.number_input("FiO2 (%)", step=1.0, value=None, key="n_fio2")
        lac = st.number_input("Lactate", step=0.1, value=None, key="n_lac")
    with c_t2:
        hb = st.number_input("Hb", step=0.1, value=None, key="n_hb")
        co = st.number_input("CO", step=0.1, value=None, key="n_co")
        spo2 = st.number_input("SpO2", step=1.0, value=None, key="n_spo2")
    with c_t3:
        ph = st.number_input("pH", step=0.01, format="%.2f", value=None, key="n_ph")
        svo2 = st.number_input("SvO2", step=1.0, value=None, key="n_svo2")

    # 計算
    pf_val = None; do2_val = None; o2er_val = None
    if pao2 is not None and fio2 is not None and fio2 > 0:
        pf_val = pao2 / (fio2/100.0)
    if hb is not None and co is not None and spo2 is not None and pao2 is not None:
        cao2 = (1.34 * hb * (spo2/100)) + (0.0031 * pao2)
        do2_val = co * cao2 * 10
        if svo2 is not None:
            cvo2 = (1.34 * hb * (svo2/100)) + (0.0031 * 40)
            vo2_val = co * (cao2 - cvo2) * 10
            if do2_val > 0: o2er_val = (vo2_val / do2_val) * 100

    # プレビュー
    preview_cols = st.columns(3)
    if pf_val is not None: preview_cols[0].metric("P/F", f"{pf_val:.0f}")
    if do2_val is not None: preview_cols[1].metric("DO2", f"{do2_val:.0f}")
    if o2er_val is not None: preview_cols[2].metric("O2ER", f"{o2er_val:.1f}%")

    # 記録ボタン
    if st.button("💾 グラフに記録 (Add Point)", key="btn_record"):
        if current_patient_id not in st.session_state['patient_db']:
            st.session_state['patient_db'][current_patient_id] = []
        
        record = {
            "Time": datetime.now().strftime("%H:%M:%S"),
            "P/F": pf_val, "DO2": do2_val, "O2ER": o2er_val,
            "Lactate": lac, "pH": ph, "Hb": hb, "CO": co # 生データも保存しておく
        }
        st.session_state['patient_db'][current_patient_id].append(record)
        st.success("Recorded!")
        st.rerun()

    # グラフ描画
    history = st.session_state['patient_db'].get(current_patient_id, [])
    if len(history) > 0:
        df = pd.DataFrame(history)
        g1, g2 = st.columns(2)
        with g1:
            st.caption("Respiratory & Metab (P/F, O2ER, Lac)")
            st.line_chart(df.set_index("Time")[["P/F", "O2ER", "Lactate"]])
        with g2:
            st.caption("Hemodynamics (DO2, Hb)")
            st.line_chart(df.set_index("Time")[["DO2", "Hb"]]) # Hbの変化も見る
    else:
        st.info("データがありません。")

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
