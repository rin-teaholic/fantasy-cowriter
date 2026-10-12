import os
import streamlit as st
from auth import check_password
from agents import get_agents
from workflows import run_setting_proposal, run_setting_creation, run_novel_writing
from tools.gdocs_tool import ReadGoogleDocTool, AppendGoogleDocTool

# --- 画面の基本設定 ---
st.set_page_config(page_title="Fantasy Co-Writer", page_icon="✍️", layout="centered")

# --- パスワード保護機能 ---
if not check_password():
    st.stop()

# --- 環境変数の設定 ---
os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
DOCUMENT_ID = st.secrets["DOCUMENT_ID"]
MODEL = "gemini/gemini-3.5-flash-lite"

# --- 画面UI ---
st.title("✍️ Fantasy Co-Writer")
mode = st.radio("🎯 動作モードを選択してください", ["🛠️ 設定構築モード", "📖 小説執筆モード"], horizontal=True)

# --- 状態の初期化 ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "こんにちは！Co-Writerチームです。\n上部でモードを選んでから話しかけてください。"}]
if "doc_content" not in st.session_state:
    st.session_state.doc_content = ""
if "current_draft" not in st.session_state:
    st.session_state.current_draft = ""

# --- ツールとエージェントの準備 ---
@st.cache_resource
def init_tools():
    return ReadGoogleDocTool(), AppendGoogleDocTool()

read_tool, append_tool = init_tools()
agents = get_agents(MODEL)

# 初回読み込み
if not st.session_state.doc_content:
    with st.spinner("Googleドキュメントを読み込み中..."):
        st.session_state.doc_content = read_tool._run(document_id=DOCUMENT_ID)

# チャット描画
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ユーザー入力
user_input = st.chat_input("メッセージを入力...")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner(f"{mode} でAIチームが思考中..."):
            
            # 【共通処理】保存指示の場合
            if user_input.lower() in ['y', 'ok', 'はい', '保存', '保存して']:
                if st.session_state.current_draft:
                    target_tab = "co_writer_crewによる追加設定" if "設定" in mode else "co_writer_crewによる小説本文"
                    prefix = "■ 追加設定" if "設定" in mode else "■ 小説本文"
                    
                    append_tool._run(
                        document_id=DOCUMENT_ID,
                        text=f"{prefix}\n{st.session_state.current_draft}",
                        target_tab_title=target_tab
                    )
                    reply = f"🎉 ドキュメントに保存しました！（保存先タブ: {target_tab}）\n\n次に進めますか？"
                    st.session_state.doc_content += f"\n\n{st.session_state.current_draft}"
                    st.session_state.current_draft = ""
                else:
                    reply = "保存する文章がまだありません。"
                
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})

            # 🛠️ モード1: 設定構築モード
            elif "設定" in mode:
                if "提案" in user_input or ("テーマ" in user_input and len(user_input) < 15):
                    raw_result = run_setting_proposal(agents, st.session_state.doc_content)
                    reply = f"【ディレクターからの提案】\n{raw_result}"
                else:
                    history_text = "".join([f"【{'ユーザー' if msg['role']=='user' else 'AI'}】\n{msg['content']}\n\n" for msg in st.session_state.messages[-5:-1]])
                    raw_result = run_setting_creation(agents, st.session_state.doc_content, history_text, user_input)
                    st.session_state.current_draft = raw_result
                    reply = f"{raw_result}\n\n---\n**💡 この設定をドキュメントに保存しますか？**\n（保存する場合は「はい」、修正する場合は指示を入力してください）"
                
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})

            # 📖 モード2: 小説執筆モード
            else:
                history_text = "".join([f"【{'ユーザー' if msg['role']=='user' else 'AI'}】\n{msg['content']}\n\n" for msg in st.session_state.messages[-5:-1]])
                raw_result = run_novel_writing(agents, st.session_state.doc_content, history_text, user_input)
                st.session_state.current_draft = raw_result
                reply = f"{raw_result}\n\n---\n**💡 この本文をドキュメントに保存しますか？**\n（保存する場合は「はい」、修正する場合は「もう少し会話を増やして」のように指示してください）"
                
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})