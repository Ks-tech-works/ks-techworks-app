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
    <div class="footer">K's Research Assistant | Silent Search Mode</div>
    """, unsafe_allow_html=True)

st.title("🎓 K's Research Assistant")
st.caption("研究・論文検索支援システム (AI無駄話カット版)")

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

# --- 掃除用関数 ---
def clean_queries(raw_text):
    """AIが喋った余計な言葉を削除して、純粋な検索ワードだけリストにする"""
    lines = raw_text.strip().split('\n')
    clean_list = []
    for line in lines:
        # 余計な記号や挨拶を消す
        line = re.sub(r'^[0-9]+\.\s*', '', line) # "1. " を消す
        line = re.sub(r'^-\s*', '', line)       # "- " を消す
        line = line.strip()
        
        # 明らかに検索ワードじゃない行（挨拶など）はスキップ
        if not line: continue
        if "承知" in line or "検索ワード" in line or "以下の" in line or "切り口" in line:
            continue
        
        clean_list.append(line)
    return clean_list[:3] # 最大3つまで

# ==========================================
# 3. 分析ロジック
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
            
            # --- Phase 1: 精密検索 ---
            with st.spinner("検索戦略を立案中..."):
                kw_prompt = f"""
                ユーザーの研究テーマを調査するため、DuckDuckGoで検索する「3つの検索クエリ」を作成せよ。
                【テーマ】{my_theme}
                【詳細】{search_query}
                
                【絶対命令】
                - 挨拶や解説は一切不要。
                - 3行のテキストのみを出力すること。
                - 1行につき1つの検索クエリを書くこと。
                - 専門用語の羅列にすること（助詞は省く）。

                出力例:
                車載DC-ACインバータ 医療機器 適合性
                人工呼吸器 動作電圧範囲 JIS規格
                災害時 在宅人工呼吸療法 電源 マニュアル
                """
                kw_res = model_kw.generate_content(kw_prompt)
                
                # ★ここでAIの無駄話をカット！
                queries = clean_queries(kw_res.text)
                
                st.info(f"🗝️ 実行する検索: {queries}")

            # 検索実行
            if not queries:
                st.warning("キーワード生成に失敗しました。バックアップ検索を行います。")
                queries = [f"{my_theme[:10]} 論文"]

            with DDGS() as ddgs:
                progress_bar = st.progress(0)
                for i, q in enumerate(queries):
                    with st.spinner(f"検索中 ({i+1}/{len(queries)}): {q}"):
                        time.sleep(random.uniform(1.0, 2.0)) # 休憩
                        # 日本限定で検索
                        res = list(ddgs.text(q, region='jp-jp', max_results=2))
                        
                        # 0件なら世界検索
                        if not res:
                            res = list(ddgs.text(q, region=None, max_results=2))

                        for r in res:
                            if r['href'] not in unique_urls:
                                unique_urls.add(r['href'])
                                search_results_text += f"Title: {r['title']}\nURL: {r['href']}\nSummary: {r['body']}\n\n"
                    progress_bar.progress((i + 1) / len(queries))
                progress_bar.empty()

            # --- Phase 2: リカバリー (それでも0件なら) ---
            if not search_results_text:
                st.warning("⚠️ 詳細検索ヒットなし。キーワードを単純化して再試行...")
                simple_q = "災害医療 電源確保 ガイドライン" # 固定の安全策
                
                with st.spinner(f"再検索中: {simple_q}"):
                    with DDGS() as ddgs:
                        res = list(ddgs.text(simple_q, region='jp-jp', max_results=3))
                        for r in res:
                            search_results_text += f"Title: {r['title']}\nURL: {r['href']}\nSummary: {r['body']}\n\n"

        except Exception as e:
            st.error(f"検索プロセスエラー: {e}")

        # --- 最終判定 ---
        if not search_results_text:
            st.error("❌ 検索結果が見つかりませんでした。")
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
