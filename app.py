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
# 1. 脳みそ (人命最優先・厳格仕様)
# ==========================================
KUSANO_BRAIN = """
あなたは、市立長浜病院・臨床工学技術科次長「草野（Kusano）」です。
提供された情報を統合し、臨床のプロとして診断推論を行ってください。

【⚠️ 最重要・絶対遵守ルール (Life Safety)】
1. **「知ったかぶり」は医療事故の元と心得よ**:
   - あなたの出力は人の生死に関わります。検索結果（Search Results）や入力データにない情報を、想像で補完して「事実」として語ることは厳禁です。
   - 根拠が不十分な場合は、無理に診断せず「エビデンス不足のため判断できません」と警告してください。

2. **エビデンス・ファースト**:
   - 治療方針を提案する際は、必ず検索された「ガイドライン」や「信頼できる文献」を根拠としてください。
   - 検索結果の出典（Source）を明記し、情報の信頼性を担保してください。

3. **バイアスの徹底排除**:
   - 「既往歴があるから今回も同じ」という思い込みを捨て、トレンドデータの矛盾（急変の兆候）を見逃さないでください。

【回答フォーマット】
1. **Clinical Summary**: 患者の状態要約（客観的事実のみ）
2. **Integrated Assessment**: 病歴×数値トレンド×検索結果の統合見解
3. **Evidence**: 根拠とした文献（※検索結果になければ「なし」と明記）
4. **Plan**: 推奨アクション（優先順位をつけて具体的数値で指示）
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
    st.caption("Mode: Medical Safety First")

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
            selected_model_name = st.selectbox("使用モデル", model_list, index=default_index)
        except: st.error("Model Error")

    st.markdown("---")
    patient_id_input = st.text_input("🆔 患者ID (半角英数)", value="TEST1", max_chars=10)
    
    if patient_id_input:
        if not re.match(r'^[a-zA-Z0-9]+$', patient_id_input):
            st.error("⚠️ 英数字のみ")
        else:
            current_patient_id = patient_id_input.upper()
            st.success(f"Login: {current_patient_id}")
            
            # --- 保存・読込 ---
            st.markdown("### 💾 データ管理")
            current_data = st.session_state['patient_db'].get(current_patient_id, [])
            
            if current_data:
                json_str = json.dumps(current_data, indent=2, default=str, ensure_ascii=False)
                st.download_button("📥 データを保存", json_str, f"{current_patient_id}.json", "application/json", key="dl_btn")
            else:
                st.info("※数値を記録すると保存ボタンが出ます")
                st.button("📥 データなし", disabled=True, key="dl_btn_d")
            
            uploaded_file = st.file_uploader("📤 データを復元", type=["json"], key="up_btn")
            if uploaded_file:
                try:
                    loaded_data = json.load(uploaded_file)
                    st.session_state['patient_db'][current_patient_id] = loaded_data
                    st.success(f"復元成功 ({len(loaded_data)}件)")
                    if st.button("🔄 反映"): st.rerun()
                except: pass
            
            st.markdown("---")
            if st.button("🗑️ 履歴消去", key="del_btn"):
                st.session_state['patient_db'][current_patient_id] = []
                st.rerun()

# ==========================================
# 4. メイン画面
# ==========================================
st.title(f"👨‍⚕️ {APP_TITLE}")

if not current_patient_id:
    st.stop()

st.caption(f"Patient: **{current_patient_id}**")
tab1, tab2 = st.tabs(["📝 総合診断 (Safety Check)", "📈 トレンド管理"])

# === TAB 2: トレンド管理 ===
with tab2:
    st.info("数値入力 (必要な項目のみ)")
    
    # 呼吸・循環・代謝
    st.caption("▼ 呼吸・循環・代謝")
    c1, c2, c3 = st.columns(3)
    pao2 = c1.number_input("PaO2", step=1.0, value=None, key="n_pao2")
    fio2 = c1.number_input("FiO2", step=1.0, value=None, key="n_fio2")
    lac = c1.number_input("Lactate", step=0.1, value=None, key="n_lac")
    
    hb = c2.number_input("Hb", step=0.1, value=None, key="n_hb")
    co = c2.number_input("CO", step=0.1, value=None, key="n_co")
    spo2 = c2.number_input("SpO2", step=1.0, value=None, key="n_spo2")
    
    ph = c3.number_input("pH", step=0.01, value=None, key="n_ph")
    svo2 = c3.number_input("SvO2", step=1.0, value=None, key="n_svo2")

    # 電解質・AG
    st.caption("▼ 電解質 (AG計算用)")
    e1, e2, e3, e4 = st.columns(4)
    na = e1.number_input("Na", step=1.0, value=None, key="n_na")
    cl = e2.number_input("Cl", step=1.0, value=None, key="n_cl")
    hco3 = e3.number_input("HCO3", step=0.1, value=None, key="n_hco3")
    alb = e4.number_input("Alb", step=0.1, value=None, key="n_alb")

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
        if alb: c_ag = ag + 2.5 * (4.0 - alb) # 補正AG

    # プレビュー
    cols = st.columns(4)
    if pf: cols[0].metric("P/F", f"{pf:.0f}")
    if do2: cols[1].metric("DO2", f"{do2:.0f}")
    if o2er: cols[2].metric("O2ER", f"{o2er:.1f}%")
    if c_ag: cols[3].metric("AG(補正)", f"{c_ag:.1f}")
    elif ag: cols[3].metric("AG(実測)", f"{ag:.1f}")

    if st.button("💾 記録"):
        if current_patient_id not in st.session_state['patient_db']: st.session_state['patient_db'][current_patient_id] = []
        
        record = {
            "Time": datetime.now().strftime("%H:%M:%S"),
            "P/F": pf, "DO2": do2, "O2ER": o2er, 
            "Lactate": lac, "Hb": hb, "pH": ph,
            "AG": c_ag if c_ag else ag
        }
        st.session_state['patient_db'][current_patient_id].append(record)
        st.rerun()
    
    # グラフ
    hist = st.session_state['patient_db'].get(current_patient_id, [])
    if hist:
        df = pd.DataFrame(hist)
        target_cols = ["P/F", "DO2", "O2ER", "Lactate", "Hb", "pH", "AG"]
        for col in target_cols:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
        
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("##### 呼吸・代謝 (P/F, O2ER, Lac)")
            st.line_chart(df.set_index("Time")[["P/F", "O2ER", "Lactate"]])
        with g2:
            st.markdown("##### 酸塩基・循環 (AG, pH, DO2)")
            st.line_chart(df.set_index("Time")[["AG", "pH", "DO2"]])
        
        with st.expander("🔍 生データ"): st.dataframe(df)

# === TAB 1: 総合診断 (Smart Search & Safety) ===
with tab1:
    col1, col2 = st.columns(2)
    hist_text = col1.text_area("病歴")
    lab_text = col1.text_area("検査データ")
    up_file = col2.file_uploader("画像", accept_multiple_files=True)

    if st.button("🔍 診断実行"):
        if not api_key:
            st.error("APIキーを入れてください")
        else:
            trend_str = "なし"
            hist = st.session_state['patient_db'].get(current_patient_id, [])
            if hist: trend_str = pd.DataFrame(hist).tail(5).to_markdown(index=False)
            
            # 1. 検索 (Smart Search)
            search_context = ""
            search_key = ""
            try:
                model_kw = genai.GenerativeModel(model_name=selected_model_name)
                # 病名推定も含めて検索ワードを作らせる
                kw_res = model_kw.generate_content(f"以下の情報から医学的検索語を3つ抽出(スペース区切り)。記号不可。\n{hist_text[:100]}\n{lab_text[:100]}")
                search_key = kw_res.text.strip()
                with st.spinner(f"エビデンス確認中... ({search_key})"):
                    with DDGS() as ddgs:
                        # 日本語医学情報を優先
                        results = list(ddgs.text(f"{search_key} ガイドライン", region='jp-jp', max_results=3))
                        for i, r in enumerate(results): search_context += f"Title: {r['title']}\nURL: {r['href']}\nBody: {r['body']}\n\n"
            except Exception as e:
                search_context = f"(検索システムエラー: {e})"

            # 2. 生成
            prompt = f"""
            情報を統合分析せよ。
            【病歴】{hist_text}
            【検査】{lab_text}
            【トレンド】{trend_str}
            【検索結果 (Evidence)】{search_context}
            """
            
            content = [prompt]
            if up_file:
                for f in up_file: content.append(Image.open(f))

            try:
                model = genai.GenerativeModel(model_name=selected_model_name, system_instruction=KUSANO_BRAIN)
                with st.spinner("診断推論中..."):
                    res = model.generate_content(content)
                
                # --- 結果のパースと表示 ---
                raw = res.text
                
                st.markdown("### 👨‍⚕️ Assessment Result")
                st.write(raw) # 万が一パースできなくても全文は表示

                # 責任表示
                st.warning("⚠️ **【重要】本システムは診断支援AIです。最終的な医療判断は必ず医師が行ってください。**")

                # 根拠事実 (アコーディオン)
                if search_context and "エラー" not in search_context:
                    with st.expander("📚 エビデンス・参照データ (Fact)"):
                        st.text(search_context)
                elif "エラー" in search_context:
                    st.error("⚠️ 検索機能が動作しませんでした。AIの推論のみの回答です。")

            except Exception as e:
                st.error(f"Error: {e}")
