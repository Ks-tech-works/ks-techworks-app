import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
import re
import json
from datetime import datetime
from duckduckgo_search import DDGS

# ==========================================
# 0. アプリ設定 & MERA仕様デザイン (Based on V2.7 High Contrast)
# ==========================================
COMPANY_NAME = "K's tech works. (K&G solution)"
APP_TITLE = "Super Clinical Decision Support [PRO]"

st.set_page_config(page_title=APP_TITLE, layout="wide", page_icon="🫀")

# --- CSS: 医療用モニター風のUI/UX（V2.7のデザインを完全維持） ---
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
# 1. KUSANO_BRAIN (Original Base + Section 5 Added)
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

5. **【追加規定】VV-ECMO Flow Dynamics (The 60% Rule & High SvO2)**:
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

【回答セクション構成】

---SECTION_PLAN_EMERGENCY---
**【🚨 最優先・緊急アクション (Do Now)】**
生命維持のため、今この瞬間に動くべきタスク。主語（医師、看護師、CE、薬剤師）を明確に。
※Flow Ratioに基づく指示（流量UP vs CO抑制 vs 輸血）もここに含めること。

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
# 3. サイドバー
# ==========================================
with st.sidebar:
    st.title("⚙️ SYSTEM CONFIG")
    st.caption("STATUS: PROTOTYPE v2.8 (Full)")

    try:
        api_key = st.
