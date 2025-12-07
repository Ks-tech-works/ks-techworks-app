import streamlit as st
import google.generativeai as genai
import pandas as pd
from duckduckgo_search import DDGS
import time

# ==========================================
# 0. アプリ設定
# ==========================================
st.set_page_config(page_title="K's Research Assistant", layout="wide", page_icon="🎓")

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
    <div class="footer">K's Research Assistant | Eco Mode (Limit Bypass)</div>
    """, unsafe_allow_html=True)

st.title("🎓 K's Research Assistant")
st.caption("研究・論文検索支援システム (クォータ制限回避版)")

# ==========================================
# 1. サイドバー
# ==========================================
selected_model_name = None

with st.sidebar:
    st.header("⚙️ 設定")
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", None)
        if not api_key:
            api_key = st.text_input("Gemini API Key", type="password")
        else:
            st.success("API Key Loaded!")
    except:
        api_key = st.text_input("Gemini API Key", type="password")

    if api_key:
        genai.configure(api_key=api_key)
        try:
            model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            # ★ 1.5-flashを最優先 (2.5は制限がきつい場合があるため)
            default_index = 0
            for i, m_name in enumerate(model_list):
                if "gemini-1.5-flash" in m_name:
                    default_index = i
                    break
            selected_model_name = st.selectbox("使用AIモデル", model_list, index=default_index)
        except: st.error("モデルエラー")

# ==========================================
# 2. メイン入力エリア
# ==========================================
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📌 研究テーマ")
    my_theme = st.text_area(
        "研究の背景・目的",
        height=150,
        value="災害時停電下において、車のシガーソケット(DC12V)からインバータを介して「人工呼吸器」と「吸引機」を同時稼働させる際の安全性評価。"
    )

with col2:
    st.subheader("🔎 知りたいこと")
    search_query = st.text_area(
        "検索したいキーワード",
        height=150,
        value="車載インバータ 医療機器 適合性\n人工呼吸器 電圧降下\n吸引機 サージ電力"
    )

# ==========================================
# 3. 分析ロジック (Ecoモード: AI呼び出しを1回に削減)
# ==========================================
if st.button("🚀 検索 & 分析開始 (Eco)", type="primary"):
    if not api_key:
        st.error("APIキーを入れてください")
    else:
        search_context = ""
        
        # --- 1. Pythonで検索ワードを作る (AIを使わない = 節約) ---
        # 入力されたテキストから改行などを処理してリスト化
        raw_keywords = search_query.replace("\n", " ").split()
        # 最初の3単語くらいを使って検索する
        base_keyword = " ".join(raw_keywords[:5]) 
        
        search_keywords = f"{base_keyword} 論文 ガイドライン" # 学術っぽくする魔法の言葉
        st.info(f"🗝️ 自動生成キーワード: **{search_keywords}**")

        # --- 2. 検索実行 (DuckDuckGo) ---
        try:
            with st.spinner(f"文献検索中..."):
                with DDGS() as ddgs:
                    # 日本限定 + HTMLモード
                    results = list(ddgs.text(search_keywords, region='jp-jp', max_results=5, backend='html'))
                    
                    if not results:
                        st.warning("ヒットなし。範囲を広げて再検索...")
                        time.sleep(1)
                        results = list(ddgs.text(search_keywords, region='wt-wt', max_results=5, backend='html'))

                    if not results:
                        st.error("❌ 検索結果なし。キーワードを短くしてみてください。")
                        st.stop()

                    for i, r in enumerate(results):
                        search_context += f"【文献{i+1}】\nTitle: {r['title']}\nURL: {r['href']}\nBody: {r['body']}\n\n"

        except Exception as e:
            st.error(f"検索エラー: {e}")
            st.stop()

        # --- 3. 分析実行 (ここで初めてAIを使う！) ---
        # これで1クリックにつき1回しか消費しないので、エラーが出にくくなる
        prompt = f"""
        あなたは優秀な研究パートナーです。
        以下の情報を統合分析してください。

        【研究テーマ】{my_theme}
        【検索結果】{search_context}

        【命令】
        1. 検索結果に含まれる情報を事実として扱い、研究にどう活かせるか提案してください。
        2. 文献のタイトルとURLを引用元として明記してください。
        """
        
        try:
            model = genai.GenerativeModel(selected_model_name)
            with st.spinner("分析中... (AI呼び出し消費: 1)"):
                res = model.generate_content(prompt)
            
            st.markdown("### 📊 分析レポート")
            st.write(res.text)
            
            with st.expander("📚 参照した文献ソース"):
                st.text(search_context)

        except Exception as e:
            st.error(f"AIエラー (429が出たら1分待ってください): {e}")
