import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
import re
import json
from datetime import datetime
from duckduckgo_search import DDGS # 安定のDuckDuckGoを使用

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
    /* スマホで見やすいように調整 */
    p, li {{ font-size: 16px !important; }}
    .stAlert {{ font-weight: bold; }}
    </style>
    <div class="footer">Produced by {COMPANY_NAME}</div>
    """, unsafe_allow_html=True)

# # ==========================================
# 1. 脳みそ (6職種連携 + 世界標準 + 攻めの集中治療仕様)
# ==========================================
KUSANO_BRAIN = """
あなたは、高度救命救急センターの「統括司令塔（Medical Commander）」としての役割を持つAI「草野」です。
**「多職種連携（Interprofessional Work）」**を前提とし、各専門職の能力を最大限に引き出す指示を出してください。

【プロフェッショナルの役割定義】
以下の役割に基づき、単なる作業指示ではなく「評価・提案・管理」を含めた指示を行うこと。
1. **【医師 (MD)】**: 診断、治療方針の最終決定、侵襲的手技、家族へのIC。
2. **【看護師 (NS)】**: 患者の微細な変化（顔色、苦痛）の早期検知、鎮静・鎮痛評価、家族ケア、感染管理。
3. **【臨床工学技士 (CE)】**: 機器（人工呼吸器, VA-ECMO, VV-ECMO, CRRT）を用いた生体機能の代行と最適化。**LV Unloading (左室負荷軽減)**や酸素需給バランスの観点から設定変更を提案。
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
   - 例: 「胃残が多いなら、**幽門後栄養 (Post-pyloric Feeding)**チューブを留置して栄養を開始せよ」

3. **安全と禁忌**:
   - 不安定な循環動態（低CO/低BP）の患者に対して、**体位変換（腹臥位など）は緊急アクションに含まない**こと。
   - **「やってはいけないこと (Do Not)」**を明確に警告せよ。

4. **現場のリアリティ**:
   - スマホ閲覧を想定し、結論ファーストで簡潔に。「検討する」ではなく「準備する」「開始する」と断定せよ。

【回答セクション構成】

---SECTION_PLAN_EMERGENCY---
**【🚨 最優先・緊急アクション (Do Now)】**
生命維持のため、今この瞬間に動くべきタスク。主語（医師、看護師、CE、薬剤師）を明確に。

---SECTION_AI_OPINION---
**【🧠 病態推論・クロスオーバー分析】**
- トレンドデータの乖離（DO2 vs Lactateなど）から読み取れる隠れた病態。
- 負の連鎖（臓器不全の悪循環）の特定。
- **治療のジレンマと解決策**。
- **⚠️ Do Not（禁忌・注意）**。

---SECTION_PLAN_ROUTINE---
**【✅ 継続管理・詳細プラン (Do Next)】**
チーム全体（栄養、リハ、薬剤調整）で取り組むべき管理方針。

---SECTION_FACT---
**【📚 エビデンス・根拠】**
検索結果に基づくガイドラインや文献の引用。
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
    st.caption("Mode: Stable DuckDuckGo")

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
                st.info("※記録すると保存ボタンが出現")
                st.button("📥 データなし", disabled=True, key="dl_btn_d")
            
            uploaded_file = st.file_uploader("📤 データを復元", type=["json"], key="up_btn")
            if uploaded_file:
                try:
                    loaded_data = json.load(uploaded_file)
                    st.session_state['patient_db'][current_patient_id] = loaded_data
                    st.success(f"復元成功 ({len(loaded_data)}件)")
                    if st.button("🔄 グラフ反映"): st.rerun()
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
tab1, tab2 = st.tabs(["📝 総合診断 (Stable)", "📈 トレンド管理"])

# === TAB 2: トレンド管理 (AG・電解質・グラフ修正完備) ===
with tab2:
    st.info("数値入力")
    
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
        if alb: c_ag = ag + 2.5 * (4.0 - alb)

    # プレビュー
    cols = st.columns(4)
    if pf: cols[0].metric("P/F", f"{pf:.0f}")
    if do2: cols[1].metric("DO2", f"{do2:.0f}")
    if o2er: cols[2].metric("O2ER", f"{o2er:.1f}%")
    if c_ag: cols[3].metric("AG(補)", f"{c_ag:.1f}")
    elif ag: cols[3].metric("AG", f"{ag:.1f}")

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
    
    # --- グラフ描画 (修正済) ---
    hist = st.session_state['patient_db'].get(current_patient_id, [])
    if hist:
        df = pd.DataFrame(hist)
        
        target_cols = ["P/F", "DO2", "O2ER", "Lactate", "Hb", "pH", "AG"]
        for col in target_cols:
            if col not in df.columns: df[col] = None
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("##### 呼吸・代謝")
            available_cols1 = [c for c in ["P/F", "O2ER", "Lactate"] if df[c].notna().any()]
            if available_cols1: st.line_chart(df.set_index("Time")[available_cols1])
            
        with g2:
            st.markdown("##### 酸塩基・循環")
            available_cols2 = [c for c in ["AG", "pH", "DO2"] if df[c].notna().any()]
            if available_cols2: st.line_chart(df.set_index("Time")[available_cols2])
        
        with st.expander("🔍 生データ確認"): st.dataframe(df)

# === TAB 1: 総合診断 (DuckDuckGo + 修正済) ===
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
            
            if hist: 
                trend_str = pd.DataFrame(hist).tail(5).to_markdown(index=False)
            
            # --- 1. DuckDuckGoで検索実行 ---
            search_context = ""
            search_key = ""
            try:
                # 検索ワード生成
                model_kw = genai.GenerativeModel(model_name=selected_model_name)
                kw_res = model_kw.generate_content(f"以下の情報から医学的検索語を3つ抽出(スペース区切り)。記号不可。\n{hist_text[:100]}\n{lab_text[:100]}")
                search_key = kw_res.text.strip()
                
                with st.spinner(f"検索中... ({search_key})"):
                    with DDGS() as ddgs:
                        results = list(ddgs.text(f"{search_key} ガイドライン", region='jp-jp', max_results=3))
                        for i, r in enumerate(results): search_context += f"Title: {r['title']}\nURL: {r['href']}\nBody: {r['body']}\n\n"
            except Exception as e:
                search_context = f"(検索エラー: {e})"

            # --- 2. AIへプロンプト ---
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
                # 3. AI実行
                model = genai.GenerativeModel(model_name=selected_model_name, system_instruction=KUSANO_BRAIN)
                with st.spinner("診断推論中..."):
                    res = model.generate_content(content)
                
                # --- 結果のパースと表示 ---
                raw = res.text
                parts_emer = raw.split("---SECTION_PLAN_EMERGENCY---")
                parts_ai   = raw.split("---SECTION_AI_OPINION---")
                parts_rout = raw.split("---SECTION_PLAN_ROUTINE---")
                parts_fact = raw.split("---SECTION_FACT---")

                if len(parts_emer) > 1:
                    emer_content = parts_emer[1].split("---SECTION")[0].strip()
                    st.error(f"🚨 **【最優先・緊急アクション】**\n\n{emer_content}", icon="⚡")

                if len(parts_ai) > 1:
                    ai_content = parts_ai[1].split("---SECTION")[0].strip()
                    st.warning(f"🤔 **【病態評価・推論】**\n\n{ai_content}", icon="🧠")

                if len(parts_rout) > 1:
                    rout_content = parts_rout[1].split("---SECTION")[0].strip()
                    st.info(f"✅ **【管理方針・検査オーダー】**\n\n{rout_content}", icon="📋")

                if len(parts_fact) > 1:
                    fact_content = parts_fact[1].split("---SECTION")[0].strip()
                    with st.expander("📚 エビデンス・参照データ (Fact)"):
                        st.markdown(fact_content)
                        if search_context and "エラー" not in search_context:
                             st.text(search_context)

                if "---SECTION" not in raw: st.write(raw)
                
                st.warning("⚠️ **【重要】本システムは診断支援AIです。最終的な医療判断は必ず医師が行ってください。**")

            except Exception as e:
                st.error(f"Error: {e}")
