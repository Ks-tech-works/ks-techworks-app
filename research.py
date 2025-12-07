import streamlit as st
import google.generativeai as genai
from duckduckgo_search import DDGS
import time
import random
import re

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
    <div class="footer">K's Research Assistant | Flash Speed Mode</div>
    """, unsafe_allow_html=True)

st.title("🎓 K's Research Assistant")
st.caption("研究・論文検索支援システム (高速・連打対応版)")

# ==========================================
# 1. サイドバー (設定 & Flash優先)
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
        
        # ★ここが修正ポイント：Flashモデルを優先的に探す
        try:
            model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            default_index = 0
            for i, m_name in enumerate(model_list):
                # "flash" が名前に含まれるものを優先選択 (429エラー回避)
                if "gemini-1.5-flash" in m_name:
                    default_index = i
                    break
            selected_model_name = st.selectbox("使用AIモデル", model_list, index=default_index)
        except Exception as e:
            st.error(f"モデルリスト取得エラー: {e}")

# ==========================================
# 2. メイン入力エリア
# ==========================================
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📌 研究テーマ・背景")
    my_theme = st.text_area(
        "実験の目的や前提条件",
        height=200,
        value="災害時停電下において、車のシガーソケット(DC12V)からインバータを介して「人工呼吸器」と「吸引機」を同時稼働させる際の安全性評価。\n特に突入電流による電圧降下で機器が停止しないかを検証したい。"
    )

with col2:
    st.subheader("🔎 知りたい技術的詳細")
    search_query = st.text_area(
        "検索したい具体的な項目",
        height=200,
        value="・車載インバータの変換効率と医療機器への適合性\n・人工呼吸器の許容電圧範囲\n・吸引機の起動時サージ電力\n・災害時電源確保のガイドライン"
    )

# ==========================================
# 3. 分析ロジック
# ==========================================
if st.button("🚀 検索 & 分析開始", type="primary"):
    if not api_key or not my_theme or not search_query:
        st.error("入力欄をすべて埋めてください。")
    elif not selected_model_name:
        st.error("モデルが選択されていません。")
    else:
        search_context = ""
        search_keywords = ""
        
        try:
            model_kw = genai.GenerativeModel(selected_model_name)
            
            # --- Try 1: 検索ワード生成 ---
            with st.spinner("検索ワードを考案中..."):
                kw_prompt = f"""
                以下の研究テーマを調査するため、DuckDuckGoで検索するための「最適な検索クエリ」を1つだけ作成してください。
                【テーマ】{my_theme}
                【詳細】{search_query}
                
                【条件】
                - 3〜5個の専門用語をスペース区切りで並べる。
                - 助詞や記号は省く。
                - 出力は検索クエリのみ。

                例: 車載インバータ 医療機器 突入電流 災害時
                """
                kw_res = model_kw.generate_content(kw_prompt)
                search_keywords = kw_res.text.strip()
                st.info(f"🗝️ 検索キーワード: **{search_keywords}**")

            # --- Try 1: 検索実行 ---
            with st.spinner(f"文献検索中... (Try 1)"):
                with DDGS() as ddgs:
                    try:
                        # 日本限定 + HTMLモードでブロック回避
                        results = list(ddgs.text(search_keywords, region='jp-jp', max_results=5, backend='html'))
                    except:
                        results = []

            # --- Try 2: 失敗時、AIにワードを作り直させる ---
            if not results:
                st.warning("⚠️ 詳細検索でヒットしませんでした。AIがキーワードを再構成します...")
                
                with st.spinner("検索ワードを再考中..."):
                    retry_prompt = f"""
                    先ほどの検索クエリ「{search_keywords}」では検索結果が0件でした。
                    同じテーマで、よりヒットしやすい、一般的で広い意味の検索クエリを1つ作成し直してください。
                    【条件】専門用語を少し減らし、一般的な用語にする。出力はクエリのみ。
                    """
                    retry_res = model_kw.generate_content(retry_prompt)
                    retry_keywords = retry_res.text.strip()
                    st.info(f"🗝️ 再検索ワード: **{retry_keywords}**")

                with st.spinner(f"再検索中... (Try 2)"):
                    time.sleep(1) # 休憩
                    with DDGS() as ddgs:
                        try:
                            # 範囲を広げて再検索
                            results = list(ddgs.text(retry_keywords, region='wt-wt', max_results=5, backend='html'))
                        except:
                            results = []

            # --- 結果処理 ---
            if not results:
                st.error("❌ 検索結果が見つかりませんでした。テーマの表現を変えてみてください。")
                st.stop()

            for i, r in enumerate(results):
                search_context += f"【文献{i+1}】\nTitle: {r['title']}\nURL: {r['href']}\nSummary: {r['body']}\n\n"

        except Exception as e:
            st.error(f"検索システムエラー: {e}")
            st.stop()

        # --- 分析実行 ---
        prompt = f"""
        あなたは優秀な大学院生の研究パートナーです。
        以下の「検索結果」を読み込み、「ユーザーの研究テーマ」に対する有用性を分析してください。

        【ユーザーの研究テーマ】
        {my_theme}

        【検索された文献リスト】
        {search_context}

        【命令】
        1. 検索結果に含まれる情報のみを事実として扱うこと（ハルシネーション禁止）。
        2. 研究テーマに対して、どの文献のどのデータが役立つか具体的に指摘すること。

        【出力フォーマット】
        ## 📊 文献分析レポート
        ### 1. 検索結果の要約
        ### 2. 研究への活用ポイント
        - **[タイトル]**: (活用法・要約)
        ### 3. 次のアクション提案
        """

        try:
            model = genai.GenerativeModel(selected_model_name)
            with st.spinner("文献を分析中..."):
                response = model.generate_content(prompt)
            
            st.markdown(response.text)
            
            with st.expander("📚 参照した文献ソース"):
                st.text(search_context)

        except Exception as e:
            st.error(f"AI分析エラー: {e}")
