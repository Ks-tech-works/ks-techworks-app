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
    <div class="footer">K's Research Assistant | Academic Mode</div>
    """, unsafe_allow_html=True)

st.title("🎓 K's Research Assistant")
st.caption("大学院研究・論文検索支援システム (ハルシネーション防止版)")

# ==========================================
# 1. サイドバー (設定)
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
            # モデル自動取得
            model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            default_index = 0
            for i, m_name in enumerate(model_list):
                if "gemini-1.5-pro" in m_name:
                    default_index = i
                    break
            selected_model_name = st.selectbox("使用AIモデル", model_list, index=default_index)
        except Exception as e:
            st.error(f"モデルエラー: {e}")

# ==========================================
# 2. メイン入力エリア
# ==========================================
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📌 研究テーマ・背景")
    my_theme = st.text_area(
        "実験の目的や前提条件",
        height=200,
        placeholder="例：\n災害時停電下において、車のシガーソケット(DC12V)からインバータを介して「人工呼吸器」と「吸引機」を同時稼働させる際の安全性評価。\n特に突入電流による電圧降下で機器が停止しないかを検証したい。"
    )

with col2:
    st.subheader("🔎 知りたい技術的詳細")
    search_query = st.text_area(
        "検索したい具体的な項目",
        height=200,
        placeholder="例：\n・車載インバータの変換効率と医療機器への適合性\n・人工呼吸器の許容電圧範囲\n・吸引機の起動時サージ電力\n・災害時電源確保のガイドライン"
    )

# ==========================================
# 3. 分析ロジック (学術検索強化版)
# ==========================================
if st.button("🚀 学術検索 & 分析開始", type="primary"):
    if not api_key or not my_theme or not search_query:
        st.error("入力欄をすべて埋めてください。")
    elif not selected_model_name:
        st.error("モデルが選択されていません。")
    else:
        # --- A. 検索キーワード生成 (ここを厳格化！) ---
        final_keywords = ""
        try:
            model_kw = genai.GenerativeModel(selected_model_name)
            
            with st.spinner("専門用語を抽出して検索ワードを構築中..."):
                # ★名言集などを排除するための「学術指定プロンプト」
                kw_prompt = f"""
                あなたは理工学・医学系の専門リサーチャーです。
                ユーザーの研究テーマに関連する「学術論文」「技術仕様書」「ガイドライン」を検索するための、最適な検索クエリを作成してください。

                【研究テーマ】{my_theme}
                【知りたいこと】{search_query}

                【絶対ルール】
                1. 一般的な用語は避け、専門用語（例: "DC-ACインバータ", "サージ電流", "J-SSCG", "性能評価"）を使うこと。
                2. ノイズ（ブログや名言集）を除外するため、クエリの末尾に必ず **"論文 OR ガイドライン OR 仕様書"** を付与すること。
                3. 出力は「検索クエリ文字列」のみとする。（解説不要）
                
                出力例: 車載DC-ACインバータ 医療機器 適合性 論文 OR ガイドライン
                """
                kw_res = model_kw.generate_content(kw_prompt)
                final_keywords = kw_res.text.strip()
                st.info(f"🔑 使用する検索クエリ: **{final_keywords}**")

        except Exception as e:
            st.error(f"キーワード生成エラー: {e}")
            st.stop()

        # --- B. DuckDuckGoで検索 ---
        search_results_text = ""
        try:
            with st.spinner("論文・技術情報を検索中... (DuckDuckGo)"):
                with DDGS() as ddgs:
                    # 日本語の情報を優先検索
                    results = list(ddgs.text(final_keywords, region='jp-jp', max_results=5))
                    
                    if not results:
                        st.warning("検索結果が0件でした。条件を緩めて再検索します...")
                        # バックアップ検索（キーワードを単純化）
                        backup_query = f"{search_query[:20]} 医療 論文"
                        results = list(ddgs.text(backup_query, region='jp-jp', max_results=3))

                    for i, r in enumerate(results):
                        search_results_text += f"【文献{i+1}】\nTitle: {r['title']}\nURL: {r['href']}\nSummary: {r['body']}\n\n"
        except Exception as e:
            st.error(f"検索エンジンエラー: {e}")
            st.stop()

        if not search_results_text:
            st.error("有効な情報が見つかりませんでした。検索ワードを変えて試してください。")
            st.stop()

        # --- C. Geminiで分析 (RAG) ---
        prompt = f"""
        あなたは優秀な大学院生の研究パートナー（Ph.D.候補生レベル）です。
        以下の「検索された文献」を読み込み、「ユーザーの研究テーマ」に対する有用性を分析してください。

        【ユーザーの研究テーマ】
        {my_theme}

        【検索された文献リスト】
        {search_results_text}

        【命令】
        1. **ハルシネーション厳禁**: 検索結果に含まれる情報のみを事実として扱ってください。
        2. **関連性評価**: もし検索結果が「名言」や「無関係なブログ」だった場合は、「役に立つ情報はありませんでした」と正直に報告し、嘘の分析をしないでください。
        3. **活用アドバイス**: 有用な文献があれば、それを実験や論文執筆にどう活かせるか具体的に提案してください。

        【出力フォーマット】
        ## 📊 文献分析レポート
        
        ### 1. 検索結果の概要
        (ヒットした情報の質について評価)

        ### 2. 研究への活用ポイント
        - **[文献タイトル]**: 
            - 💡 **活用法**: 
            - 📝 **内容要約**: 
        
        ### 3. 次のアクション提案
        (実験計画の修正案や、追加で調べるべきパラメータなど)
        """

        try:
            model = genai.GenerativeModel(selected_model_name)
            with st.spinner("文献を精査・分析中..."):
                response = model.generate_content(prompt)
            
            st.markdown(response.text)
            
            with st.expander("📚 参照した文献ソース (Raw Data)"):
                st.text(search_results_text)

        except Exception as e:
            st.error(f"AI分析エラー: {e}")
