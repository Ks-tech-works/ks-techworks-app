import streamlit as st
import google.generativeai as genai
from duckduckgo_search import DDGS

# ==========================================
# 0. アプリ設定
# ==========================================
st.set_page_config(page_title="K's Research Assistant", layout="wide", page_icon="🎓")

st.title("🎓 K's Research Assistant")
st.caption("Smart Literature Search & Analysis | Powered by Gemini 1.5 Pro")

# ==========================================
# 1. サイドバー (設定 & モデル選択)
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
            selected_model_name = st.selectbox("使用するAIモデル", model_list, index=default_index)
        except Exception as e:
            st.error(f"モデルリスト取得エラー: {e}")

# ==========================================
# 2. メイン入力エリア
# ==========================================
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📌 あなたの研究テーマ")
    my_theme = st.text_area(
        "研究の背景・目的など",
        height=150,
        placeholder="例：\n災害時における在宅人工呼吸器の電源確保。\n車のシガーソケットからDC/ACインバータ経由で稼働させる際の実用性と安全性を検証したい。"
    )

with col2:
    st.subheader("🔎 調べたいトピック")
    search_query = st.text_area(
        "具体的に知りたいこと（箇条書きでもOK）",
        height=150,
        placeholder="例：\nシガーソケットの最大出力電流\n正弦波インバータと矩形波の違い\n医療機器の電圧許容範囲"
    )

# ==========================================
# 3. 分析ロジック (スマート検索実装)
# ==========================================
if st.button("🚀 スマート検索 & 分析開始", type="primary"):
    if not api_key or not my_theme or not search_query:
        st.error("入力欄をすべて埋めてください。")
    elif not selected_model_name:
        st.error("AIモデルを選択してください。")
    else:
        # --- A. 検索キーワードの生成 (AI) ---
        final_keywords = ""
        try:
            # キーワード生成用モデル
            model_kw = genai.GenerativeModel(selected_model_name)
            
            with st.spinner("最適な検索ワードを考案中..."):
                kw_prompt = f"""
                あなたは優秀なリサーチャーです。
                ユーザーの研究テーマと知りたいことから、検索エンジン(DuckDuckGo)で最も質の高い学術情報・技術情報がヒットするような「検索キーワード」を3〜4単語で作成してください。

                【研究テーマ】{my_theme}
                【知りたいこと】{search_query}

                【条件】
                - 文章ではなく、スペース区切りの単語にする。
                - 「論文」「ガイドライン」「仕様書」「実験データ」などの単語を含めると良い。
                - 余計な解説は不要。キーワードのみ出力すること。
                """
                kw_res = model_kw.generate_content(kw_prompt)
                final_keywords = kw_res.text.strip()
                st.info(f"🔑 生成された検索ワード: **{final_keywords}**")

        except Exception as e:
            st.error(f"キーワード生成エラー: {e}")
            st.stop()

        # --- B. DuckDuckGoで検索 ---
        search_results = ""
        try:
            with st.spinner(f"文献を検索中... ({final_keywords})"):
                with DDGS() as ddgs:
                    # 日本語の学術・技術情報を優先
                    results = list(ddgs.text(f"{final_keywords}", region='jp-jp', max_results=5))
                    
                    if not results:
                        st.warning("検索結果が0件でした。キーワードを変えて再試行します...")
                        # バックアップ：単純なキーワードで再検索
                        results = list(ddgs.text(f"{search_query[:20]} 論文", region='jp-jp', max_results=3))

                    for i, r in enumerate(results):
                        search_results += f"【文献{i+1}】\nTitle: {r['title']}\nURL: {r['href']}\nSummary: {r['body']}\n\n"
        except Exception as e:
            st.error(f"検索エンジンエラー: {e}")
            st.stop()

        if not search_results:
            st.error("検索結果が見つかりませんでした。入力内容を少し変えてみてください。")
            st.stop()

        # --- C. Geminiで分析 (RAG) ---
        prompt = f"""
        あなたは優秀な大学院生の研究パートナー（Ph.D.候補生レベル）です。
        以下の「検索された文献」を読み込み、「ユーザーの研究テーマ」にとってどのような価値があるかを分析してください。

        【ユーザーの研究テーマ】
        {my_theme}

        【検索された文献リスト】
        {search_results}

        【命令】
        1. **ハルシネーション厳禁**: 検索結果に含まれる情報のみを事実として扱ってください。
        2. **関連性分析 (最重要)**: 「この文献のどのデータが、ユーザーの研究の参考になるか？」を具体的に指摘してください。
        3. **引用**: 必ず情報の出所（文献タイトル/URL）を明記してください。

        【出力フォーマット】
        ## 📊 文献分析レポート
        
        ### 1. 検索結果の概要 (Summary)
        (ヒットした情報の傾向と要点)

        ### 2. 研究への活用ポイント (Insights)
        - **[文献タイトル]**
            - 💡 **活用法**: （例：〇〇の数値データは、実験の比較対象として使えます）
            - 📝 **要約**: （内容の簡潔なまとめ）
        
        ### 3. 次に調べるべきこと
        (今回の検索で足りなかった情報や、次に検索すべきキーワードの提案)
        """

        try:
            model = genai.GenerativeModel(selected_model_name)
            with st.spinner("論文と研究テーマを照合・分析中..."):
                response = model.generate_content(prompt)
            
            st.markdown(response.text)
            
            with st.expander("📚 参照した文献ソース (Raw Data)"):
                st.text(search_results)

        except Exception as e:
            st.error(f"AI分析エラー: {e}")
