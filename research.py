import streamlit as st
import google.generativeai as genai
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
    <div class="footer">K's Research Assistant | Simple & Robust</div>
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
        value="車載インバータ 医療機器 適合性\n人工呼吸器 電圧降下"
    )

# ==========================================
# 3. 分析ロジック (医療アプリと同じ構造)
# ==========================================
if st.button("🚀 検索 & 分析開始", type="primary"):
    if not api_key:
        st.error("APIキーを入れてください")
    else:
        search_context = ""
        search_keywords = ""
        
        try:
            # 1. 検索ワード生成 (AI)
            model_kw = genai.GenerativeModel(selected_model_name)
            
            with st.spinner("検索ワードを考案中..."):
                # ★医療アプリと同じシンプルな指示に戻す
                kw_prompt = f"""
                以下の研究テーマから、検索エンジンでヒットしやすいキーワードを1行だけ作成してください。
                【テーマ】{my_theme} {search_query}
                
                【条件】
                - 3〜4単語のスペース区切り。
                - 専門用語すぎるとヒットしないので、一般的だが核心を突く言葉を選ぶこと。
                - 出力は検索クエリのみ。

                例: 災害時 医療機器 電源確保
                """
                kw_res = model_kw.generate_content(kw_prompt)
                search_keywords = kw_res.text.strip()
                st.info(f"🗝️ 検索キーワード: **{search_keywords}**")

            # 2. 検索実行 (DuckDuckGo)
            with st.spinner(f"文献検索中..."):
                with DDGS() as ddgs:
                    # ★backend='html' を指定 (これがブロック回避の鍵)
                    results = list(ddgs.text(search_keywords, region='jp-jp', max_results=5, backend='html'))
                    
                    # 0件なら世界で検索 (リカバリー)
                    if not results:
                        st.warning("国内で見つからなかったため、範囲を広げて再検索します...")
                        time.sleep(1)
                        results = list(ddgs.text(search_keywords, region='wt-wt', max_results=5, backend='html'))

                    if not results:
                        st.error("❌ 検索結果が見つかりませんでした。キーワードを変更してみてください。")
                        st.stop()

                    for i, r in enumerate(results):
                        search_context += f"【文献{i+1}】\nTitle: {r['title']}\nURL: {r['href']}\nSummary: {r['body']}\n\n"

        except Exception as e:
            st.error(f"検索システムエラー: {e}")
            st.stop()

        # 3. 分析実行 (AI)
        prompt = f"""
        あなたは優秀な大学院生の研究パートナーです。
        以下の情報を統合分析してください。

        【研究テーマ】{my_theme}
        【知りたいこと】{search_query}
        【検索結果】{search_context}

        【命令】
        1. 検索結果に含まれる情報を事実として扱い、研究にどう活かせるか提案してください。
        2. 検索結果がテーマとずれている場合は、その旨を指摘し、一般的な知識で補足してください。

        【出力フォーマット】
        ## 📊 文献分析レポート
        ### 1. 検索結果の要約
        ### 2. 研究への活用ポイント
        - **[タイトル]**: (活用法・要約)
        ### 3. 次のアクション提案
        """
        
        try:
            model = genai.GenerativeModel(selected_model_name)
            with st.spinner("分析中..."):
                res = model.generate_content(prompt)
            
            st.markdown(res.text)
            
            with st.expander("📚 参照した文献ソース"):
                st.text(search_context)

        except Exception as e:
            st.error(f"AIエラー: {e}")
