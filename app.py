import os
import time
import streamlit as st
from crewai import Agent, Task, Crew, Process
from tools.gdocs_tool import ReadGoogleDocTool, AppendGoogleDocTool

# --- 画面の基本設定 ---
st.set_page_config(page_title="Fantasy Co-Writer", page_icon="✍️", layout="centered")

# --- パスワード保護機能 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    st.title("🔒 ログイン")
    pwd_input = st.text_input("パスワードを入力してください", type="password")
    if st.button("ログイン"):
        if pwd_input == st.secrets["APP_PASSWORD"]:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("パスワードが正しくありません")
    return False

if not check_password():
    st.stop() # パスワードが合っていなければここで処理を停止

# --- 0. 環境変数の設定 (Secretsから取得) ---
os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]

# --- 1. メイン画面のタイトル表示 ---
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

director = Agent(
    role="進行役ディレクター", 
    goal="ユーザーと対話して次に深掘りすべき設定のテーマを提案する", 
    backstory="優秀な編集者。", 
    llm=MODEL, 
    verbose=False
)

idea_generator = Agent(
    role="アイデアデザイナー", 
    goal="ユーザーの指示に基づいて具体的な設定案の初期ドラフトを作成・修正する", 
    backstory="発想力豊かな設定の専門家。自由で魅力的なアイデアを生み出す。", 
    llm=MODEL, 
    verbose=False
)

# ★ 新規追加: 設定監修・校閲エージェント
checker = Agent(
    role="設定監修・校閲エージェント",
    goal="提案された設定案の言語的表現・ニュアンスの適切さを検証し、既存設定との矛盾を解消して最終案を完成させる",
    backstory="ファンタジー世界観の整合性と多言語・文化表現に精通したベテラン校閲者。細かな設定の矛盾を見逃さず、より具体的にブラッシュアップする。",
    llm=MODEL,
    verbose=False
)

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
        with st.spinner("AIチームが思考・検証中...（数秒〜数十秒かかります）"):
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

            # パターンC: 具体案の作成・検証・校閲指示（2ステップ処理）
            else:
                history_text = ""
                for msg in st.session_state.messages[-5:-1]:
                    speaker = "ユーザー" if msg["role"] == "user" else "AI"
                    history_text += f"【{speaker}】\n{msg['content']}\n\n"

                # Step 1: アイデアデザイナーが原案を作成
                task_generate = Task(
                    description=(
                        f"既存設定:\n{st.session_state.doc_content[:3000]}\n\n"
                        f"直近の会話の流れ:\n{history_text}\n"
                        f"ユーザーの最新の指示:\n{user_input}\n\n"
                        f"上記の会話の流れを踏まえて、具体的で魅力的な設定案の初期ドラフトを作成してください。"
                    ), 
                    expected_output="設定案の初期ドラフト", 
                    agent=idea_generator
                )

                # Step 2: 校閲エージェントが言語・矛盾・解像度をチェックして完成させる
                task_check = Task(
                    description=(
                        f"既存設定:\n{st.session_state.doc_content[:3000]}\n\n"
                        f"アイデアデザイナーが作成した初期ドラフトを受け取り、以下の基準でチェックおよび修正を行ってください：\n"
                        f"1. 【言語・表現チェック】国ごとの使用言語（英語・ドイツ語等）や単語のニュアンス、固有名詞の響きが世界観に適切か精査し修正する。\n"
                        f"2. 【設定の整合性】既存設定と矛盾している点がないか確認し、矛盾があれば整合性を取る。\n"
                        f"3. 【解像度の向上】発動条件・コスト・リスク・視覚的イメージを具体化し、物語のフックとなる要素を加える。\n\n"
                        f"修正・ブラッシュアップが完了した最終的な設定案のみを出力してください。"
                    ),
                    expected_output="チェック・修正済みの完成された設定案",
                    agent=checker
                )

                # 2つのエージェントを順に実行
                result = Crew(
                    agents=[idea_generator, checker], 
                    tasks=[task_generate, task_check], 
                    process=Process.sequential
                ).kickoff()

                st.session_state.current_draft = result.raw
                
                reply = f"{result.raw}\n\n---\n**💡 この内容でドキュメントに保存しますか？**\n（保存する場合は「はい」、修正する場合は「もっとダークにして」のように入力してください）"
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})