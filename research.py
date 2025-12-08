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
    <div class="footer">K's Research Assistant | High Speed Mode</div>
    """, unsafe_allow_html=True)

st.title("🎓 K's Research Assistant")
st.caption("研究・論文検索支援システム (DuckDuckGo v6対応版)")

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
            # Flashを優先
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
# 3. 分析ロジック (診断アプリの成功パターンを移植)
# ==========================================
if st.button("🚀 検索 & 分析開始", type="primary"):
    if not api_key:
        st.error("APIキーを入れてください")
        st.stop()

    search_context = ""
    # 検索キーワード作成
    simple_keywords = search_query.replace("\n", " ") + " 論文 ガイドライン J-STAGE"
    
    st.info(f"🔍 検索中... ({simple_keywords})")

    try:
        # ==========================================================
        # ★ここが修正ポイント！診断アプリと同じ書き方に変更
        # backend='html' を削除し、region='jp-jp' を明示
        # ==========================================================
        with DDGS() as ddgs:
            # 診断アプリ同様、list()で即時取得
            results = list(ddgs.text(simple_keywords, region='jp-jp', max_results=5))
            
            # 国内でヒットしなかった場合の救済措置（ワールドワイド検索）
            if not results:
                st.warning("国内検索でヒットなし。範囲を広げます...")
                time.sleep(1)
                results = list(ddgs.text(simple_keywords, region='wt-wt', max_results=5))

            if not results:
                st.error("❌ 検索結果が見つかりませんでした。")
                st.stop()

            for i, r in enumerate(results):
                # bodyがない場合のエラー回避も追加
                title = r.get('title', 'No Title')
                href = r.get('href', '#')
                body = r.get('body', r.get('snippet', 'No Content'))
                search_context += f"【文献{i+1}】\nTitle: {title}\nURL: {href}\nSummary: {body}\n\n"

    except Exception as e:
        st.error(f"検索システムエラー: {e}")
        st.stop()

    # 2. 分析実行
    prompt = f"""
    あなたは優秀な大学院生の研究パートナーです。
    以下の情報を統合分析してください。

    【研究テーマ】{my_theme}
    【知りたいこと】{search_query}
    【検索結果】{search_context}

    【命令】
    1. 検索結果に含まれる情報を事実として扱い、研究にどう活かせるか提案してください。
    2. 特にインバータの「波形（正弦波・矩形波）」や「電力容量」に関する記述があれば重点的に拾ってください。
    """
    
    try:
        model = genai.GenerativeModel(selected_model_name)
        with st.spinner("分析中..."):
            response = model.generate_content(prompt)
        
        st.markdown("### 📊 分析レポート")
        st.write(response.text)
        
        with st.expander("📚 参照した文献ソース"):
            st.text(search_context)

    except Exception as e:
        st.error(f"AI生成エラー: {e}")
