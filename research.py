import streamlit as st
import google.generativeai as genai
from duckduckgo_search import DDGS
import time # ★休憩用

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
    <div class="footer">K's Research Assistant | Robust Mode</div>
    """, unsafe_allow_html=True)

st.title("🎓 K's Research Assistant")
st.caption("複合検索＆多角的分析システム (ブロック回避版)")

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
# 3. 分析ロジック (堅牢化版)
# ==========================================
if st.button("🚀 マルチ検索 & 分析開始", type="primary"):
    if not api_key or not my_theme or not search_query:
        st.error("入力欄をすべて埋めてください。")
    elif not selected_model_name:
        st.error("モデルが選択されていません。")
    else:
        # --- A. 検索キーワード生成 (3つの視点) ---
        queries = []
        try:
            model_kw = genai.GenerativeModel(selected_model_name)
            
            with st.spinner("検索戦略を立案中..."):
                kw_prompt = f"""
                あなたは専門リサーチャーです。
                ユーザーの研究テーマを調査するために、検索エンジン(DuckDuckGo)で検索すべき「3つの異なる切り口」の検索クエリを作成してください。

                【テーマ】{my_theme}
                【詳細】{search_query}

                【条件】
                1. 1つのクエリは3〜4単語程度の「短い専門用語の羅列」にする（長すぎるとヒットしないため）。
                2. 以下の3つの視点で作成すること。
                   - 視点1: 電源・工学的視点（インバータ、電圧、波形など）
                   - 視点2: 医療機器・スペック視点（人工呼吸器、電力、JISなど）
                   - 視点3: 運用・ガイドライン視点（災害医療、マニュアルなど）
                3. 出力形式は、3行のテキストのみ（番号や解説は不要）。

                例:
                車載 DC-ACインバータ 正弦波 医療機器
                人工呼吸器 動作電圧範囲 許容変動
                災害時 在宅人工呼吸療法 電源確保
                """
                kw_res = model_kw.generate_content(kw_prompt)
                raw_queries = kw_res.text.strip().split('\n')
                queries = [q.strip() for q in raw_queries if q.strip()]
                
                st.info("🗝️ **生成された検索戦略:**")
                for q in queries:
                    st.write(f"- `{q}`")

        except Exception as e:
            st.error(f"キーワード生成エラー: {e}")
            st.stop()

        # --- B. DuckDuckGoでマルチ検索 (ブロック回避ロジック) ---
        search_results_text = ""
        unique_urls = set()

        try:
            progress_bar = st.progress(0)
            
            # セッションを都度作り直すことでブロックを回避
            for i, query in enumerate(queries):
                with st.spinner(f"検索実行中 ({i+1}/{len(queries)}): {query}"):
                    try:
                        # 2秒待機 (重要！これでブロックを防ぐ)
                        time.sleep(2)
                        
                        with DDGS() as ddgs:
                            # まず日本限定でトライ
                            results = list(ddgs.text(query, region='jp-jp', max_results=3))
                            
                            # 0件なら地域制限を外して再トライ
                            if not results:
                                time.sleep(1)
                                results = list(ddgs.text(query, region=None, max_results=3))

                            for r in results:
                                if r['href'] not in unique_urls:
                                    unique_urls.add(r['href'])
                                    search_results_text += f"【文献】\nTitle: {r['title']}\nURL: {r['href']}\nSummary: {r['body']}\n\n"
                    except Exception as loop_e:
                        st.warning(f"クエリ「{query}」でエラー: {loop_e}")
                        continue
                
                progress_bar.progress((i + 1) / len(queries))
            
            progress_bar.empty()

        except Exception as e:
            st.error(f"検索エンジンエラー: {e}")

        # --- C. 最後の砦 (それでも0件ならバックアップ検索) ---
        if not search_results_text:
            st.warning("詳細検索でヒットしませんでした。簡易検索を実行します...")
            try:
                time.sleep(2)
                with DDGS() as ddgs:
                    # 非常にシンプルなワードで再検索
                    simple_q = f"{search_query[:15]} 論文"
                    results = list(ddgs.text(simple_q, region='jp-jp', max_results=3))
                    for r in results:
                        search_results_text += f"【文献(簡易)】\nTitle: {r['title']}\nURL: {r['href']}\nSummary: {r['body']}\n\n"
            except: pass

        if not search_results_text:
            st.error("有効な情報が見つかりませんでした。時間を置いて試すか、キーワードを短くしてみてください。")
            st.stop()

        # --- D. Geminiで分析 (RAG) ---
        prompt = f"""
        あなたは優秀な大学院生の研究パートナー（Ph.D.候補生レベル）です。
        以下の「複数の検索結果」を統合し、「ユーザーの研究テーマ」に対する有用性を分析してください。

        【ユーザーの研究テーマ】
        {my_theme}

        【検索された文献リスト】
        {search_results_text}

        【命令】
        1. **ハルシネーション厳禁**: 検索結果に含まれる情報のみを事実として扱ってください。
        2. **情報の統合**: 複数の検索結果から、共通するリスク（例：矩形波インバータの問題点など）や、重要な数値を抽出してください。
        3. **活用アドバイス**: 実験計画や論文執筆にどう活かせるか具体的に提案してください。

        【出力フォーマット】
        ## 📊 統合分析レポート
        
        ### 1. 検索結果の要約 (Key Findings)
        (検索全体から判明した重要な事実)

        ### 2. 研究への活用ポイント
        - **[技術的課題]**: （例：短形波インバータでは医療機器が誤作動するリスクについて...）
            - 🔗 根拠: [文献タイトル/URL]
        - **[実験パラメータ]**: （例：測定すべき電圧変動の範囲について...）
            - 🔗 根拠: [文献タイトル/URL]
        
        ### 3. 次のアクション提案
        (実験機材の選定や、測定項目の追加提案など)
        """

        try:
            model = genai.GenerativeModel(selected_model_name)
            with st.spinner("文献を精査・統合分析中..."):
                response = model.generate_content(prompt)
            
            st.markdown(response.text)
            
            with st.expander("📚 参照した全文献ソース (Raw Data)"):
                st.text(search_results_text)

        except Exception as e:
            st.error(f"AI分析エラー: {e}")
