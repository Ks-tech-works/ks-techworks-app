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
    <div class="footer">K's Research Assistant | Aggressive Search Mode</div>
    """, unsafe_allow_html=True)

st.title("🎓 K's Research Assistant")
st.caption("研究・論文検索支援システム (執念の検索版)")

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
    lines = raw_text.strip().split('\n')
    clean_list = []
    for line in lines:
        line = re.sub(r'^[0-9]+\.\s*', '', line)
        line = re.sub(r'^-\s*', '', line)
        line = line.strip()
        if not line: continue
        if "承知" in line or "検索ワード" in line or "以下の" in line: continue
        clean_list.append(line)
    return clean_list[:3]

# --- ★執念の再検索関数★ ---
def aggressive_search(ddgs, query):
    """
    ヒットするまで単語を減らして検索し続ける関数
    例: "A B C D" -> 0件 -> "A B C" -> 0件 -> "A B" -> ヒット！
    """
    words = query.split()
    
    # 元のクエリでトライ
    results = list(ddgs.text(query, region='jp-jp', max_results=3))
    if results: return results, query

    # ダメなら地域制限を外す
    results = list(ddgs.text(query, region=None, max_results=3))
    if results: return results, query + " (世界検索)"

    # それでもダメなら単語を減らしていく
    while len(words) > 1:
        words.pop() # 末尾を削除
        new_query = " ".join(words)
        time.sleep(1) # サーバー負荷軽減
        results = list(ddgs.text(new_query, region='jp-jp', max_results=3))
        if results: return results, new_query
    
    return [], "失敗"

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
            
            # --- Phase 1: 戦略立案 ---
            with st.spinner("検索戦略を立案中..."):
                kw_prompt = f"""
                ユーザーの研究テーマを調査するため、DuckDuckGoで検索する「3つの検索クエリ」を作成せよ。
                【テーマ】{my_theme}
                【詳細】{search_query}
                
                【絶対命令】
                - 挨拶や解説は一切不要。
                - 3行のテキストのみを出力すること。
                - 3〜4単語の専門用語の羅列にすること。

                出力例:
                車載インバータ 医療機器 適合性
                人工呼吸器 電圧降下 許容範囲
                災害医療 電源確保 ガイドライン
                """
                kw_res = model_kw.generate_content(kw_prompt)
                queries = clean_queries(kw_res.text)
                st.info(f"🗝️ 初回ターゲット: {queries}")

            # --- Phase 2: 執念の検索実行 ---
            with DDGS() as ddgs:
                progress_bar = st.progress(0)
                for i, q in enumerate(queries):
                    with st.spinner(f"検索中 ({i+1}/3): {q}"):
                        time.sleep(random.uniform(1.0, 2.0))
                        
                        # ★ここで粘り強く検索！
                        results, hit_query = aggressive_search(ddgs, q)
                        
                        if results:
                            # 検索ワードが変わっていたら通知
                            if hit_query != q:
                                st.caption(f"⚠️ `{q}` は0件だったため、`{hit_query}` で検索しました。")
                            
                            for r in results:
                                if r['href'] not in unique_urls:
                                    unique_urls.add(r['href'])
                                    search_results_text += f"Title: {r['title']}\nURL: {r['href']}\nSummary: {r['body']}\n\n"
                        else:
                            st.warning(f"❌ `{q}` は単語を減らしてもヒットしませんでした。")

                    progress_bar.progress((i + 1) / len(queries))
                progress_bar.empty()

        except Exception as e:
            st.error(f"検索プロセスエラー: {e}")

        # --- 最終判定 ---
        if not search_results_text:
            st.error("❌ 全ての検索が失敗しました。テーマをもっと一般的な言葉に書き換えてください。")
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
