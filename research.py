import os
import sys
import subprocess

# ---------------------------------------------------------
# ★サーバー環境の強制最適化 (Google検索を動かすための鍵)
# ---------------------------------------------------------
try:
    import google.generativeai
    # バージョンが古い、または入っていない場合に強制インストール
    if getattr(google.generativeai, "__version__", "0.0.0") < "0.8.3":
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "--force-reinstall", "google-generativeai==0.8.3"])
        import google.generativeai as genai
    else:
        import google.generativeai as genai
except:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "--force-reinstall", "google-generativeai==0.8.3"])
    import google.generativeai as genai

import streamlit as st

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
    <div class="footer">K's Research Assistant | Google High-Speed Mode</div>
    """, unsafe_allow_html=True)

st.title("🎓 K's Research Assistant")
st.caption("研究・論文検索支援システム (Google検索直結版)")

# ==========================================
# 1. サイドバー (設定)
# ==========================================
selected_model_name = None

with st.sidebar:
    st.header("⚙️ 設定")
    # バージョン確認 (0.8.3ならOK)
    st.caption(f"GenAI Lib: {genai.__version__}")

    try:
        # 研究用のキーを優先、なければ医療用
        api_key = st.secrets.get("GEMINI_API_KEY_RESEARCH", None)
        if not api_key:
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
            
            # ★Google検索は Proモデル の方が相性が良いので優先
            # (Flashでも動きますが、Proの方が検索ツールとの連携が強いです)
            default_index = 0
            for i, m_name in enumerate(model_list):
                if "gemini-1.5-pro" in m_name:
                    default_index = i
                    break
            selected_model_name = st.selectbox("使用AIモデル", model_list, index=default_index)
        except: st.error("モデルエラー")

# ==========================================
# 2. 入力エリア
# ==========================================
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📌 研究テーマ・背景")
    my_theme = st.text_area(
        "AIに伝えたい背景",
        height=150,
        value="AIの医療実装における課題と解決策の調査。特にハルシネーション対策とHuman-in-the-loopの重要性について。"
    )

with col2:
    st.subheader("🔎 検索キーワード")
    search_query = st.text_area(
        "Googleで検索するワード (入力通りに検索します)",
        height=150,
        value="DECIDE-AI clinical implementation nature"
    )

# ==========================================
# 3. 分析実行 (Google検索ツール使用)
# ==========================================
if st.button("🚀 Google検索 & 分析", type="primary"):
    if not api_key:
        st.error("APIキーを入れてください")
    else:
        # 入力されたワードをそのまま使う
        raw_query = search_query.replace("\n", " ").strip()

        # AIへのプロンプト
        prompt = f"""
        あなたは優秀な大学院生の研究パートナーです。
        以下の「研究テーマ」と「検索キーワード」について、Google検索機能を使って最新の情報を収集し、分析してください。

        【研究テーマ】
        {my_theme}

        【検索キーワード】
        {raw_query}

        【命令】
        1. Google検索ツールを使用して、指定されたキーワードに関連する論文、記事、ガイドラインを探してください。
        2. 検索結果に基づき、研究に役立つ具体的な数値や事実を提示してください。
        3. 論文が見つかった場合は、そのタイトルと要約を明記してください。

        【出力フォーマット】
        ## 📊 文献分析レポート
        ### 1. 検索結果の要約 (Key Findings)
        ### 2. 研究への活用ポイント
        - **[情報源のタイトル]**: 
            - 💡 **内容**: 
        ### 3. 次のアクション提案
        """

        try:
            # 1. モデル作成 (ツールなし)
            model = genai.GenerativeModel(selected_model_name)
            
            with st.spinner(f"Google検索中... 「{raw_query}」"):
                # 2. 実行時にツールを渡す (ここがGoogle検索のスイッチ)
                # DuckDuckGoではなく、Googleの頭脳を直接使います
                response = model.generate_content(
                    prompt,
                    tools=[{"google_search": {}}]
                )
            
            st.markdown(response.text)
            
            # 参照元表示 (Google Grounding)
            if response.candidates[0].grounding_metadata.search_entry_point:
                st.success("✅ Google検索成功")
                with st.expander("📚 参照したWebサイト (Source)"):
                    st.write(response.candidates[0].grounding_metadata.search_entry_point.rendered_content)
            else:
                st.warning("⚠️ 検索機能は動作しましたが、直接引用できるソースが表示されませんでした。")

        except Exception as e:
            st.error(f"エラー発生: {e}")
            if "quota" in str(e):
                st.error("※短時間の使いすぎです。1分ほど待ってから再試行してください。")
            if "Unknown field" in str(e):
                st.error("⚠️ サーバー更新中です。もう一度ボタンを押してください（2回目で成功します）")
