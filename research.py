import streamlit as st
import google.generativeai as genai
import pandas as pd
from duckduckgo_search import DDGS

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
    <div class="footer">K's Research Assistant | Proven Logic Mode</div>
    """, unsafe_allow_html=True)

st.title("🎓 K's Research Assistant")
st.caption("研究・論文検索支援システム (医療アプリ同等ロジック)")

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
            default_index = 0
            for i, m_name in enumerate(model_list):
                if "gemini-1.5-pro" in m_name:
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
        height=200,
        value="災害時停電下において、車のシガーソケット(DC12V)からインバータを介して「人工呼吸器」と「吸引機」を同時稼働させる際の安全性評価。"
    )

with col2:
    st.subheader("🔎 知りたいこと")
    search_query = st.text_area(
        "検索したい内容",
        height=200,
        value="インバータの変換効率、人工呼吸器の電圧許容範囲、吸引機のサージ電力"
    )

# ==========================================
# 3. 分析ロジック (医療アプリ完全移植)
# ==========================================
if st.button("🚀 検索 & 分析開始", type="primary"):
    if not api_key:
        st.error("APIキーを入れてください")
    else:
        # --- 1. 検索ワード生成 (医療アプリと同じシンプルな指示) ---
        search_context = ""
        search_key = ""
        try:
            model_kw = genai.GenerativeModel(model_name=selected_model_name)
            
            # ★ここ！医療アプリと同じく「3つ抽出」とシンプルに指示
            kw_prompt = f"以下の研究内容から、検索エンジンでヒットしやすいキーワードを3つ抽出してスペース区切りで出力せよ。記号不可。\n\n【テーマ】{my_theme}\n【詳細】{search_query}"
            
            kw_res = model_kw.generate_content(kw_prompt)
            search_key = kw_res.text.strip()

            # --- 2. 検索実行 (医療アプリと同じ設定) ---
            with st.spinner(f"検索中... ({search_key})"):
                with DDGS() as ddgs:
                    # 日本語の論文・技術情報を優先
                    results = list(ddgs.text(f"{search_key} 論文", region='jp-jp', max_results=3))
                    
                    if not results:
                        # 0件なら世界検索
                        results = list(ddgs.text(f"{search_key} paper", region='wt-wt', max_results=3))

                    for i, r in enumerate(results):
                        search_context += f"Title: {r['title']}\nURL: {r['href']}\nBody: {r['body']}\n\n"
        except Exception as e:
            search_context = f"(検索エラー: {e})"

        # --- 3. 分析実行 ---
        prompt = f"""
        あなたは優秀な研究パートナーです。
        以下の情報を統合分析してください。

        【研究テーマ】{my_theme}
        【知りたいこと】{search_query}
        【検索結果】{search_context}

        【命令】
        1. 検索結果に含まれる情報を事実として扱い、研究にどう活かせるか提案してください。
        2. 検索結果がテーマとずれている場合は、その旨を指摘し、一般的な知識で補足してください。
        """
        
        try:
            model = genai.GenerativeModel(model_name=selected_model_name)
            with st.spinner("分析中..."):
                res = model.generate_content(prompt)
            
            st.markdown("### 📊 分析レポート")
            st.write(res.text)
            
            if search_context and "エラー" not in search_context:
                with st.expander(f"🔍 参照した文献ソース ({search_key})"):
                    st.text(search_context)
            elif "エラー" in search_context:
                st.error("⚠️ 検索エラーが発生しました。")
            else:
                st.warning("⚠️ 検索結果が0件でした。")

        except Exception as e:
            st.error(f"Error: {e}")
