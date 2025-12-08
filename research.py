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
    <div class="footer">K's Research Assistant | Smart Search Edition</div>
    """, unsafe_allow_html=True)

st.title("🎓 K's Research Assistant")
st.caption("研究・論文検索支援システム (AIキーワード生成機能搭載)")

# ==========================================
# 1. サイドバー
# ==========================================
selected_model_name = None

with st.sidebar:
    st.header("⚙️ 設定")
    api_key = st.secrets.get("GEMINI_API_KEY", None)
    if not api_key:
        api_key = st.text_input("Gemini API Key", type="password")
    
    if api_key:
        genai.configure(api_key=api_key)
        try:
            model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
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
# 3. 分析ロジック (診断アプリと同じ「AIキーワード生成」を採用)
# ==========================================
if st.button("🚀 検索 & 分析開始", type="primary"):
    if not api_key:
        st.error("APIキーを入れてください")
        st.stop()

    search_context = ""
    status_text = st.empty()

    # ------------------------------------------------
    # STEP 1: AIによる検索キーワードの生成 (ここが重要！)
    # ------------------------------------------------
    status_text.info("🤖 最適な検索ワードを思考中...")
    
    try:
        model_kw = genai.GenerativeModel(selected_model_name)
        # 診断アプリと同じロジック：検索エンジンが理解しやすい単語に変換させる
        kw_prompt = f"""
        以下の研究テーマと疑問点から、DuckDuckGoなどの検索エンジンで論文や仕様書ヒットしやすい
        「検索キーワード」を3つ〜4つ作成し、スペース区切りで出力してください。
        
        テーマ: {my_theme}
        疑問: {search_query}
        
        条件: 余計な記号は含めない。英語の専門用語を含めると精度が上がる。
        出力例: 車載インバータ 正弦波 矩形波 医療機器
        """
        kw_res = model_kw.generate_content(kw_prompt)
        # 生成されたキーワード + おまじない
        final_keywords = kw_res.text.strip().replace("\n", " ") + " 論文 specifications"
        
    except Exception as e:
        st.error(f"キーワード生成エラー: {e}")
        st.stop()

    # ------------------------------------------------
    # STEP 2: 検索実行 (シンプル呼び出し)
    # ------------------------------------------------
    status_text.info(f"🔍 検索中... [{final_keywords}]")
    
    try:
        with DDGS() as ddgs:
            # 診断アプリと同じシンプルな呼び出し方
            results = list(ddgs.text(final_keywords, region='jp-jp', max_results=5))
            
            # 結果ゼロならワールドワイド
            if not results:
                status_text.warning("🇯🇵 国内ヒットなし... 🌏 世界検索に切り替えます")
                time.sleep(1)
                results = list(ddgs.text(final_keywords, region='wt-wt', max_results=5))

            if not results:
                st.error(f"❌ '{final_keywords}' で検索しましたが、結果が見つかりませんでした。")
                st.stop()

            for i, r in enumerate(results):
                title = r.get('title', 'No Title')
                href = r.get('href', '#')
                body = r.get('body', r.get('snippet', 'No Content'))
                search_context += f"【文献{i+1}】\nTitle: {title}\nURL: {href}\nSummary: {body}\n\n"

    except Exception as e:
        st.error(f"検索システムエラー: {e}")
        st.stop()

    # ------------------------------------------------
    # STEP 3: 分析実行
    # ------------------------------------------------
    status_text.success("✅ 文献取得完了！分析を開始します...")
    
    prompt = f"""
    あなたは優秀な大学院生の研究パートナー（臨床工学技士の視点あり）です。
    以下の情報を統合分析してください。

    【研究テーマ】{my_theme}
    【検索キーワード】{final_keywords}
    【検索結果】{search_context}

    【命令】
    1. 検索結果を基に、インバータ使用時の「波形の問題（正弦波 vs 矩形波/調整矩形波）」と「電力容量/突入電流」について解説してください。
    2. 人工呼吸器や吸引機が停止するリスクシナリオを具体的に挙げてください。
    3. 次に行うべき実機検証の実験項目を提案してください。
    """
    
    try:
        model = genai.GenerativeModel(selected_model_name)
        with st.spinner("執筆中..."):
            response = model.generate_content(prompt)
        
        status_text.empty()
        st.markdown("### 📊 分析レポート")
        st.write(response.text)
        
        with st.expander("📚 参照したWebソース"):
            st.text(search_context)

    except Exception as e:
        st.error(f"AI生成エラー: {e}")
