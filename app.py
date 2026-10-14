import os
import streamlit as st
import streamlit.components.v1 as components
from crewai import Task, Crew, Process
from auth import check_password
from agents import get_agents
from workflows import run_setting_proposal, run_setting_creation, run_novel_writing
from tools.gdocs_tool import ReadGoogleDocTool, AppendGoogleDocTool

# --- 画面の基本設定 ---
st.set_page_config(page_title="Fantasy Co-Writer", page_icon="✍️", layout="centered")

# 自動スクロール用関数
def scroll_to_bottom():
    try:
        components.html(
            """
            <script>
                var mainSection = window.parent.document.querySelector('section.main');
                if (mainSection) {
                    mainSection.scrollTo({
                        top: mainSection.scrollHeight,
                        behavior: 'smooth'
                    });
                }
            </script>
            """,
            height=0,
        )
    except Exception:
        pass

# --- パスワード保護機能 ---
if not check_password():
    st.stop()

# --- 環境変数の設定 ---
os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
DOCUMENT_ID = st.secrets["DOCUMENT_ID"]
MODEL = "gemini/gemini-3.5-flash-lite"

# --- ツールとエージェントの準備 ---
@st.cache_resource
def init_tools():
    return ReadGoogleDocTool(), AppendGoogleDocTool()

read_tool, append_tool = init_tools()
agents = get_agents(MODEL)

# --- セッション状態の初期化 ---
if "selected_mode" not in st.session_state:
    st.session_state.selected_mode = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "doc_content" not in st.session_state:
    st.session_state.doc_content = ""
if "current_draft" not in st.session_state:
    st.session_state.current_draft = ""
if "generating_response" not in st.session_state:
    st.session_state.generating_response = False

# 初回ドキュメント読み込み
if not st.session_state.doc_content:
    with st.spinner("Googleドキュメントを読み込み中..."):
        try:
            st.session_state.doc_content = read_tool._run(document_id=DOCUMENT_ID)
        except Exception as e:
            st.error(f"ドキュメントの読み込みに失敗しました: {e}")

# --- タイトルヘッダー ---
st.title("✍️ Fantasy Co-Writer")

# ==========================================
# 1. モード未選択時：タップ選択画面
# ==========================================
if st.session_state.selected_mode is None:
    st.write("### どちらの作業を行いますか？ タップして選択してください")
    col1, col2 = st.columns(2)

    # ボタン1: 設定構築モード
    with col1:
        if st.button("🛠️ 設定構築モード\n\n(世界観・国家・魔法・言語の作成)", use_container_width=True):
            st.session_state.selected_mode = "🛠️ 設定構築モード"
            with st.spinner("ディレクターが設定ドキュメントを読み込み、提案を準備中..."):
                try:
                    proposal = run_setting_proposal(agents, st.session_state.doc_content)
                    initial_msg = (
                        "👋 **ディレクターです！設定構築モードを開始します。**\n\n"
                        "既存のドキュメントを踏まえ、次に深掘りすべきテーマ案をまとめました：\n\n"
                        f"{proposal}\n\n---\n"
                        "気になるテーマの番号を入力するか、具体的に詰めたい設定を教えてください！"
                    )
                except Exception as e:
                    initial_msg = (
                        "⚠️ **Gemini APIが一時的に混雑しています（503エラーなど）。**\n\n"
                        "数十秒待ってから、画面上の「🔄 モード切替」を押して再試行してください。"
                    )
                st.session_state.messages.append({"role": "assistant", "content": initial_msg})
            st.rerun()

    # ボタン2: 小説執筆モード
    with col2:
        if st.button("📖 小説執筆モード\n\n(本文・シーン・対話の執筆)", use_container_width=True):
            st.session_state.selected_mode = "📖 小説執筆モード"
            with st.spinner("ディレクターが執筆の切り口を準備中..."):
                try:
                    director = agents["director"]
                    task = Task(
                        description=(
                            f"【既存設定】\n{st.session_state.doc_content}...\n\n"
                            f"上記の設定を踏まえ、小説本文の執筆を開始するにあたって、おすすめのシーンやエピソードの切り口を3〜4つ提案してください。"
                        ),
                        expected_output="シーン・エピソードの候補リスト",
                        agent=director
                    )
                    result = Crew(agents=[director], tasks=[task], process=Process.sequential).kickoff()
                    initial_msg = (
                        "👋 **ディレクターです！小説執筆モードを開始します。**\n\n"
                        "既存の世界観・設定をベースに、執筆を始めるおすすめのシーンをいくつかピックアップしました：\n\n"
                        f"{result.raw}\n\n---\n"
                        "書きたいシーンや指示を入力してください！"
                    )
                except Exception as e:
                    initial_msg = (
                        "⚠️ **Gemini APIが一時的に混雑しています（503エラーなど）。**\n\n"
                        "数十秒待ってから、画面上の「🔄 モード切替」を押して再試行してください。"
                    )
                st.session_state.messages.append({"role": "assistant", "content": initial_msg})
            st.rerun()

    st.stop()

# ==========================================
# 2. モード選択後：チャット画面
# ==========================================
mode_col, update_col, reset_col = st.columns([3, 2, 2])
with mode_col:
    st.info(f"**現在のモード:** {st.session_state.selected_mode}")

with update_col:
    if st.button("📄 ソース最新化", help="Googleドキュメントの最新状態を読み込み直します", use_container_width=True):
        with st.spinner("ドキュメントを再読み込み中..."):
            try:
                st.session_state.doc_content = read_tool._run(document_id=DOCUMENT_ID)
                st.toast("✅ ドキュメントを最新状態に更新しました！")
            except Exception as e:
                st.error(f"再読み込みに失敗しました: {e}")

with reset_col:
    if st.button("🔄 モード切替", help="モード選択画面に戻ります", use_container_width=True):
        st.session_state.selected_mode = None
        st.session_state.messages = []
        st.session_state.current_draft = ""
        st.session_state.generating_response = False
        st.rerun()

# チャット履歴の表示
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- AI返答処理 ---
if st.session_state.generating_response:
    with st.chat_message("assistant"):
        with st.spinner("AIチームが作業中..."):
            user_input = st.session_state.messages[-1]["content"]
            
            try:
                # 【共通処理】保存指示の場合
                if user_input.lower() in ['y', 'ok', 'はい', '保存', '保存して']:
                    if st.session_state.current_draft:
                        target_tab = "co_writer_crewによる追加設定" if "設定" in st.session_state.selected_mode else "co_writer_crewによる小説本文"
                        prefix = "■ 追加設定" if "設定" in st.session_state.selected_mode else "■ 小説本文"
                        
                        append_tool._run(
                            document_id=DOCUMENT_ID,
                            text=f"{prefix}\n{st.session_state.current_draft}",
                            target_tab_title=target_tab
                        )
                        reply = f"🎉 ドキュメントに保存しました！（保存先タブ: `{target_tab}`）\n\n次に進める内容を入力してください。"
                        st.session_state.doc_content += f"\n\n{st.session_state.current_draft}"
                        st.session_state.current_draft = ""
                    else:
                        reply = "保存する文章がまだありません。"

                # 🛠️ 設定構築モード
                elif "設定" in st.session_state.selected_mode:
                    if "提案" in user_input or ("テーマ" in user_input and len(user_input) < 15):
                        raw_result = run_setting_proposal(agents, st.session_state.doc_content)
                        reply = f"【ディレクターからの提案】\n{raw_result}"
                    else:
                        history_text = "".join([f"【{'ユーザー' if msg['role']=='user' else 'AI'}】\n{msg['content']}\n\n" for msg in st.session_state.messages[-5:-1]])
                        raw_result = run_setting_creation(agents, st.session_state.doc_content, history_text, user_input)
                        st.session_state.current_draft = raw_result
                        reply = f"{raw_result}\n\n---\n**💡 この設定をドキュメントに保存しますか？**\n（保存する場合は「はい」、修正する場合は指示を入力してください）"

                # 📖 小説執筆モード
                else:
                    history_text = "".join([f"【{'ユーザー' if msg['role']=='user' else 'AI'}】\n{msg['content']}\n\n" for msg in st.session_state.messages[-5:-1]])
                    raw_result = run_novel_writing(agents, st.session_state.doc_content, history_text, user_input)
                    st.session_state.current_draft = raw_result
                    reply = f"{raw_result}\n\n---\n**💡 この本文をドキュメントに保存しますか？**\n（保存する場合は「はい」、修正する場合は「もう少し描写を増やして」のように指示してください）"

            except Exception as e:
                reply = (
                    "⚠️ **Google Gemini API の一時的な混雑（503エラー）が発生しました。**\n\n"
                    "サーバーへのアクセスが一時的に集中しています。\n"
                    "1分ほど時間を置いてから、もう一度同じ指示を送信してみてください。"
                )

            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.session_state.generating_response = False
            scroll_to_bottom()
            st.rerun()

# --- ユーザー入力エリア ---
with st.form(key="chat_form", clear_on_submit=True):
    user_input_raw = st.text_area(
        label="メッセージ入力",
        placeholder="メッセージを入力してください（キーボードの改行で改行できます）",
        height=100,
        label_visibility="collapsed"
    )
    submit_btn = st.form_submit_button("📤 送信", type="primary", use_container_width=True)

# 送信ボタンのアクション
if submit_btn and user_input_raw.strip():
    user_input = user_input_raw.strip()
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.generating_response = True
    scroll_to_bottom()
    st.rerun()