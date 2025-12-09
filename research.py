import streamlit as st
import google.generativeai as genai
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
    <div class="footer">K's Research Assistant | Proven Stability Ver.</div>
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
        # 研究用キーがあれば優先、なければ医療用
        api_key = st.secrets.get("GEMINI_API_KEY_RESEARCH", None)
        if not api_key:
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
            # Flashを優先 (連打対策)
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
    st.subheader("📌 研究テーマ・背景")
    my_theme = st.text_area(
        "AIに伝えたい背景",
        height=200,
        value="AIの医療実装における課題と解決策の調査。特にハルシネーション対策とHuman-in-the-loopの重要性について。"
    )

with col2:
    st.subheader("🔎 検索キーワード")
    search_query = st.text_area(
        "検索したい単語 (スペース区切り)",
        height=200,
        value="DECIDE-AI clinical implementation nature"
    )

# ==========================================
# 3. 分析ロジック (医療アプリの成功ロジック)
# ==========================================
if st.button("🚀 検索 & 分析開始", type="primary"):
    if not api_key:
        st.error("APIキーを入れてください")
    else:
        search_context = ""
        
        # 1. 検索ワードの整形 (Pythonで確実に作る)
        # 余計な文字を消して、「論文」という言葉を足す
        clean_query = search_query.replace("\n", " ").strip()
        final_query = f"{clean_query} 論文" 
        
        try:
            # 2. 検索実行 (DuckDuckGo / HTMLモード)
            # これが一番ブロックされにくい最強の設定です
            with st.spinner(f"文献検索中... ({final_query})"):
                with DDGS() as ddgs:
                    # 日本限定
                    results = list(ddgs.text(final_query, region='jp-jp', max_results=5, backend='html'))
                    
                    # 0件なら世界検索 (リカバリー)
                    if not results:
                        st.warning("国内で見つからなかったので、世界中の論文を探します...")
                        results = list(ddgs.text(clean_query, region='wt-wt', max_results=5, backend='html'))

                    if not results:
                        st.error("❌ 検索結果が見つかりませんでした。キーワードを短くしてみてください。")
                        st.stop()

                    for i, r in enumerate(results):
                        search_context += f"【文献{i+1}】\nTitle: {r['title']}\nURL: {r['href']}\nSummary: {r['body']}\n\n"

        except Exception as e:
            st.error(f"検索システムエラー: {e}")
            st.stop()

        # 3. 分析実行 (AI)
        prompt = f"""
        あなたは優秀な大学院生の研究パートナーです。
        以下の検索結果を読み込み、「ユーザーの研究テーマ」に対する有用性を分析してください。

        【ユーザーの研究テーマ】
        {my_theme}

        【検索キーワード】
        {clean_query}

        【検索された文献リスト】
        {search_context}

        【命令】
        1. 検索結果に含まれる情報を事実として扱うこと。
        2. 論文や記事が見つかった場合、その概要と研究への活かし方を解説すること。

        【出力フォーマット】
        ## 📊 検索結果レポート
        ### 1. ヒットした主要文献
        - **[タイトル]** (URL)
            - 📝 **要約**: 
        ### 2. 研究への活用ポイント
        """
        
        try:
            model = genai.GenerativeModel(selected_model_name)
            with st.spinner("分析中..."):
                response = model.generate_content(prompt)
            
            st.markdown(response.text)
            
            with st.expander("📚 参照した文献ソース"):
                st.text(search_context)

        except Exception as e:
            st.error(f"AIエラー: {e}")
