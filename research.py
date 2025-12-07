import streamlit as st
import google.generativeai as genai
from duckduckgo_search import DDGS
import time
import random

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
    <div class="footer">K's Research Assistant | Recovery Mode</div>
    """, unsafe_allow_html=True)

st.title("🎓 K's Research Assistant")
st.caption("研究・論文検索支援システム (検索強化版)")

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
# 3. 分析ロジック (リカバリー検索実装)
# ==========================================
if st.button("🚀 検索 & 分析開始", type="primary"):
    if not api_key or not my_theme or not search_query:
        st.error("入力欄をすべて埋めてください。")
    elif not selected_model_name:
        st.error("モデルが選択されていません。")
    else:
        search_results_text = ""
        unique_urls = set()
        
        try:
            model_kw = genai.GenerativeModel(selected_model_name)
            
            # --- Phase 1: 精密検索 (3つの専門的クエリ) ---
            with st.spinner("検索戦略を立案中... (Phase 1)"):
                kw_prompt = f"""
                ユーザーの研究テーマを調査するため、DuckDuckGoで検索する「3つの異なる切り口」の検索クエリを作成してください。
                【テーマ】{my_theme}
                【詳細】{search_query}
                【条件】3〜4単語の専門用語の羅列。
                例: 車載DC-ACインバータ 医療機器 適合
                """
                kw_res = model_kw.generate_content(kw_prompt)
                queries = [q.strip() for q in kw_res.text.strip().split('\n') if q.strip()]
                st.info(f"🗝️ 戦略: {queries}")

            # 検索実行
            with DDGS() as ddgs:
                for q in queries:
                    with st.spinner(f"検索中: {q}"):
                        time.sleep(random.uniform(1.5, 3.0)) # ランダムな休憩でブロック回避
                        res = list(ddgs.text(q, region='jp-jp', max_results=2))
                        for r in res:
                            if r['href'] not in unique_urls:
                                unique_urls.add(r['href'])
                                search_results_text += f"Title: {r['title']}\nURL: {r['href']}\nSummary: {r['body']}\n\n"

            # --- Phase 2: リカバリー検索 (もし0件なら) ---
            if not search_results_text:
                st.warning("⚠️ 詳細検索でヒットしませんでした。キーワードを単純化して再試行します...")
                
                with st.spinner("検索ワードを再調整中... (Phase 2)"):
                    # AIに「もっと簡単なワード」を考えさせる
                    retry_prompt = f"""
                    先ほどの検索で結果が0件でした。
                    もっと一般的でヒットしやすい「広義の検索ワード」を1つだけ作成してください。
                    【テーマ】{my_theme}
                    例: 災害医療 電源確保 ガイドライン
                    """
                    retry_res = model_kw.generate_content(retry_prompt)
                    simple_query = retry_res.text.strip()
                    st.info(f"🗝️ リカバリー検索: {simple_query}")
                
                # 再検索実行
                with st.spinner(f"再検索中: {simple_query}"):
                    time.sleep(2)
                    with DDGS() as ddgs:
                        # 地域制限を外して広く探す
                        res = list(ddgs.text(simple_query, region=None, max_results=3))
                        for r in res:
                            search_results_text += f"Title: {r['title']}\nURL: {r['href']}\nSummary: {r['body']}\n\n"

        except Exception as e:
            st.error(f"検索エラー: {e}")

        # --- 最終判定 ---
        if not search_results_text:
            st.error("❌ 検索結果が見つかりませんでした。入力内容（テーマ）を少し変更してみてください。")
            st.stop()

        # --- C. Geminiで分析 ---
        prompt = f"""
        あなたは優秀な大学院生の研究パートナーです。
        以下の「検索結果」を統合し、「ユーザーの研究テーマ」に対する有用性を分析してください。

        【ユーザーの研究テーマ】
        {my_theme}

        【検索された文献リスト】
        {search_results_text}

        【命令】
        検索結果に含まれる情報のみを事実として扱い、研究への活用法を具体的に提案してください。

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
            with st.expander("📚 参照した全文献ソース"):
                st.text(search_results_text)

        except Exception as e:
            st.error(f"AI分析エラー: {e}")
