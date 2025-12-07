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
    <div class="footer">K's Research Assistant | High Speed Mode</div>
    """, unsafe_allow_html=True)

st.title("🎓 K's Research Assistant")
st.caption("研究・論文検索支援システム (災害時医療機器・電源安全性研究用)")

# ==========================================
# 1. サイドバー
# ==========================================
selected_model_name = None

with st.sidebar:
    st.header("⚙️ 設定")
    # APIキーの取得ロジック（secrets優先）
    api_key = st.secrets.get("GEMINI_API_KEY", None)
    if not api_key:
        api_key = st.text_input("Gemini API Key", type="password")
    else:
        st.success("API Key Loaded!")

    if api_key:
        try:
            genai.configure(api_key=api_key)
            # モデルリスト取得（エラーハンドリング強化）
            model_list = []
            try:
                all_models = genai.list_models()
                model_list = [m.name for m in all_models if 'generateContent' in m.supported_generation_methods]
            except Exception as e:
                st.warning(f"モデルリスト取得失敗: デフォルト設定を使用します。")
                model_list = ["models/gemini-1.5-flash", "models/gemini-1.5-pro"]

            # Flashを優先 (連打対策)
            default_index = 0
            for i, m_name in enumerate(model_list):
                if "gemini-1.5-flash" in m_name:
                    default_index = i
                    break
            
            if model_list:
                selected_model_name = st.selectbox("使用AIモデル", model_list, index=default_index)
            else:
                st.error("利用可能なモデルが見つかりません。")
        except Exception as e:
            st.error(f"API設定エラー: {e}")

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
        value="車載インバータ 正弦波 矩形波 医療機器 適合性\n人工呼吸器 電圧降下 インラッシュカレント"
    )

# ==========================================
# 3. 検索関数（リトライ機能付き）
# ==========================================
def robust_search(query, max_retries=3):
    """DuckDuckGo検索を安定させるためのリトライ関数"""
    results = []
    attempt = 0
    
    with DDGS() as ddgs:
        while attempt < max_retries:
            try:
                # backend='html' を削除 (これがエラーの主犯であることが多い)
                # max_results を少し減らして負荷を下げる
                results = list(ddgs.text(query, region='jp-jp', max_results=4))
                if results:
                    return results
                else:
                    # 国内で見つからない場合、ワールドワイドで再試行せず一旦空で返す
                    break
            except Exception as e:
                attempt += 1
                wait_time = random.uniform(1, 3) # ランダムに待機
                time.sleep(wait_time)
                # print(f"Retry {attempt}/{max_retries}: {e}") # デバッグ用
    return results

# ==========================================
# 4. 分析ロジック
# ==========================================
if st.button("🚀 検索 & 分析開始", type="primary"):
    if not api_key:
        st.error("APIキーを入れてください")
        st.stop()
    
    if not selected_model_name:
        st.error("モデルが選択されていません")
        st.stop()

    search_context = ""
    # キーワードの整形: 学術的な検索にかかりやすい単語を追加
    simple_keywords = search_query.replace("\n", " ") + " 論文 報告書 jstage"
    
    # ----------------------------------
    # 1. 検索実行
    # ----------------------------------
    status_text = st.empty()
    status_text.info(f"🔍 文献検索中... ({simple_keywords})")
    
    try:
        results = robust_search(simple_keywords)
        
        # 結果が0件だった場合の救済措置（英語検索などはせず、キーワードを変えてみるよう促す）
        if not results:
            st.warning("⚠️ 検索結果が見つかりませんでした。")
            st.info("💡 ヒント: 「インバータ 医療機器 添付文書」のようにキーワードを具体的にするか、少し減らしてみてください。")
            st.stop()

        for i, r in enumerate(results):
            # bodyがない場合はtitleを使うなどの安全策
            body_text = r.get('body', r.get('title', 'No content'))
            search_context += f"【文献{i+1}】\nTitle: {r['title']}\nURL: {r['href']}\nSummary: {body_text}\n\n"
        
        status_text.success("✅ 検索完了！分析を開始します...")
        time.sleep(0.5)

    except Exception as e:
        st.error(f"検索システムエラー: {e}")
        st.stop()

    # ----------------------------------
    # 2. 分析実行
    # ----------------------------------
    prompt = f"""
    あなたは臨床工学の専門知識を持つ大学院生の研究パートナーです。
    以下の検索結果と研究テーマに基づき、論理的かつ批判的に分析を行ってください。

    【研究テーマ】
    {my_theme}

    【ユーザーの疑問】
    {search_query}

    【検索された文献情報】
    {search_context}

    【分析レポートの構成】
    1. **サマリ**: 検索結果から得られた知見の要約（特に電源容量、波形の影響について）
    2. **リスク評価**: インバータ使用時の懸念点（電圧降下、突入電流、ノイズなど）
    3. **不足情報**: 検索結果では足りない情報と、今後検証すべき実験パラメータ
    4. **参考文献リスト**: 引用元のURL付きリスト

    です・ます調で、修士論文の研究メモとして使える品質で出力してください。
    """
    
    try:
        model = genai.GenerativeModel(selected_model_name)
        with st.spinner("🤖 AIが論文・技術情報を分析中..."):
            response = model.generate_content(prompt)
        
        status_text.empty() # ステータス消去
        
        st.markdown("### 📊 研究分析レポート")
        st.write(response.text)
        
        with st.expander("📚 参照したWebソース詳細"):
            st.text(search_context)

    except Exception as e:
        st.error(f"AI生成エラー: {e}")
