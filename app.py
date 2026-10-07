import os
import streamlit as st
from crewai import Agent, Task, Crew, Process
from tools.gdocs_tool import ReadGoogleDocTool, AppendGoogleDocTool

# --- 0. 環境変数の設定 (Secretsから取得) ---
os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]

# --- 1. 画面の基本設定 ---
st.set_page_config(page_title="Fantasy Co-Writer", page_icon="✍️", layout="centered")
st.title("✍️ Fantasy Co-Writer")

DOCUMENT_ID = st.secrets["DOCUMENT_ID"]
MODEL = "gemini/gemini-3.5-flash-lite" # エラーが出にくい安定モデル

# --- 2. 状態（記憶）の初期化 ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "こんにちは！ディレクターです。\n「テーマを提案して」と入力するか、考えたい設定（例：魔法のルールについて）を直接入力してください。"}]
if "doc_content" not in st.session_state:
    st.session_state.doc_content = ""
if "current_draft" not in st.session_state:
    st.session_state.current_draft = ""

# --- 3. ツールとエージェントの準備 ---
@st.cache_resource
def init_tools():
    return ReadGoogleDocTool(), AppendGoogleDocTool()

read_tool, append_tool = init_tools()

director = Agent(role="進行役ディレクター", goal="ユーザーと対話して次に深掘りすべき設定のテーマを提案する", backstory="優秀な編集者。", llm=MODEL, verbose=False)
idea_generator = Agent(role="アイデアデザイナー", goal="ユーザーの指示に基づいて具体的な設定案を作成・修正する", backstory="設定の専門家。", llm=MODEL, verbose=False)

# ドキュメントの初回読み込み
if not st.session_state.doc_content:
    with st.spinner("Googleドキュメントを読み込み中..."):
        st.session_state.doc_content = read_tool._run(document_id=DOCUMENT_ID)

# --- 4. チャット画面の描画 ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 5. ユーザーからの入力とAIの処理 ---
user_input = st.chat_input("メッセージを入力...")
if user_input:
    # 自分が打った文字を画面に追加
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("AIが思考中...（数秒〜数十秒かかります）"):
            # パターンA: 保存の指示
            if user_input.lower() in ['y', 'ok', 'はい', '保存', '保存して']:
                if st.session_state.current_draft:
                    res = append_tool._run(
                        document_id=DOCUMENT_ID,
                        text=f"■ 追加設定\n{st.session_state.current_draft}",
                        target_tab_title="co_writer_crewによる追加設定"
                    )
                    reply = f"🎉 ドキュメントに保存しました！\n\n次に考えたいことはありますか？"
                    st.session_state.doc_content += f"\n\n{st.session_state.current_draft}" # 記憶もアップデート
                    st.session_state.current_draft = "" # ドラフトをリセット
                else:
                    reply = "保存する提案がまだありません。まずはテーマを指定してください。"
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})

            # パターンB: 提案の指示
            elif "提案" in user_input or "テーマ" in user_input and len(user_input) < 15:
                task = Task(description=f"以下の既存設定を踏まえ、次に設定を詰めるべきテーマ案を5つ提案して。\n\n{st.session_state.doc_content[:3000]}...", expected_output="テーマの選択肢", agent=director)
                result = Crew(agents=[director], tasks=[task], process=Process.sequential).kickoff()
                reply = f"【ディレクターからの提案】\n{result.raw}"
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})

            # パターンC: 具体案の作成・修正指示
            else:
                task = Task(description=f"既存設定:\n{st.session_state.doc_content[:3000]}\n\nユーザーの指示:\n{user_input}\n\n（前回までのやり取りでの修正指示なら、それに従って直してください）\n具体的で魅力的な設定案を作成してください。", expected_output="詳細な設定案", agent=idea_generator)
                result = Crew(agents=[idea_generator], tasks=[task], process=Process.sequential).kickoff()
                st.session_state.current_draft = result.raw
                
                reply = f"{result.raw}\n\n---\n**💡 この内容でドキュメントに保存しますか？**\n（保存する場合は「はい」、修正する場合は「もっとダークにして」のように入力してください）"
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})