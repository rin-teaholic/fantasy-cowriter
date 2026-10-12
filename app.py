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

# --- 1. メイン画面のタイトルとモード選択 ---
st.title("✍️ Fantasy Co-Writer")

# 画面上部でモードを選択（スマホでも押しやすいラジオボタン）
mode = st.radio(
    "🎯 動作モードを選択してください",
    ["🛠️ 設定構築モード", "📖 小説執筆モード"],
    horizontal=True
)

DOCUMENT_ID = st.secrets["DOCUMENT_ID"]
MODEL = "gemini/gemini-3.5-flash-lite" # 安定モデル

# --- 2. 状態（記憶）の初期化 ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "こんにちは！Co-Writerチームです。\n上部でモードを選んでから話しかけてください。"}]
if "doc_content" not in st.session_state:
    st.session_state.doc_content = ""
if "current_draft" not in st.session_state:
    st.session_state.current_draft = ""

# --- 3. ツールとエージェントの準備 ---
@st.cache_resource
def init_tools():
    return ReadGoogleDocTool(), AppendGoogleDocTool()

read_tool, append_tool = init_tools()

# 【設定モード用エージェント】
director = Agent(
    role="進行役ディレクター", 
    goal="ユーザーと対話して次に深掘りすべき設定のテーマを提案する", 
    backstory="優秀な編集者。", 
    llm=MODEL, verbose=False
)
idea_generator = Agent(
    role="アイデアデザイナー", 
    goal="ユーザーの指示に基づいて具体的な設定案の初期ドラフトを作成・修正する", 
    backstory="発想力豊かな設定の専門家。自由で魅力的なアイデアを生み出す。", 
    llm=MODEL, verbose=False
)
checker = Agent(
    role="設定監修・校閲エージェント",
    goal="提案された設定案の言語的表現・ニュアンスの適切さを検証し、既存設定との矛盾を解消して最終案を完成させる",
    backstory="ファンタジー世界観の整合性と多言語・文化表現に精通したベテラン校閲者。既存ドキュメント内の『ソースの言語体系』を厳格に参照して言語表現や固有名詞を検証する。",
    llm=MODEL, verbose=False
)

# 【執筆モード用エージェント】
novel_writer = Agent(
    role="小説家・ライター",
    goal="設定ドキュメントとユーザーの指示に基づき、情景描写や感情表現豊かな小説の本文・プロットを執筆する",
    backstory="ファンタジー小説を得意とするプロ作家。キャラクターの台詞回しや世界観の描写に秀でている。",
    llm=MODEL, verbose=False
)
prose_editor = Agent(
    role="文章推敲・推稿エージェント",
    goal="執筆された小説本文の文体・リズム・五感表現・会話のテンポを磨き上げ、魅力的な完成原稿にする",
    backstory="文芸誌のベテラン文章エージェント。読者を惹きつけるテンポと描写の精緻化を行う。",
    llm=MODEL, verbose=False
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
                    
                    res = append_tool._run(
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
                # テーマ提案指示
                if "提案" in user_input or ("テーマ" in user_input and len(user_input) < 15):
                    task = Task(description=f"以下の既存設定を踏まえ、次に設定を詰めるべきテーマ案を5つ提案して。\n\n{st.session_state.doc_content[:3000]}...", expected_output="テーマの選択肢", agent=director)
                    result = Crew(agents=[director], tasks=[task], process=Process.sequential).kickoff()
                    reply = f"【ディレクターからの提案】\n{result.raw}"
                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                
                # 具体的な設定作成・修正
                else:
                    history_text = "".join([f"【{'ユーザー' if msg['role']=='user' else 'AI'}】\n{msg['content']}\n\n" for msg in st.session_state.messages[-5:-1]])
                    
                    t1 = Task(
                        description=f"既存設定:\n{st.session_state.doc_content[:3000]}\n\n会話の流れ:\n{history_text}\n最新指示:\n{user_input}\n\n具体的で魅力的な設定案の初期ドラフトを作成してください。",
                        expected_output="設定案の初期ドラフト", agent=idea_generator
                    )
                    t2 = Task(
                        description=(
                            f"既存設定:\n{st.session_state.doc_content[:3000]}\n\n"
                            f"初期ドラフトを受け取り、以下の基準でチェックおよび修正を行ってください：\n"
                            f"1. 【言語体系・表現チェック】既存設定にある『ソースの言語体系』の記述を基準とし、国ごとの使用言語（英語・ドイツ語等）、単語のニュアンス、固有名詞の綴り・響きが世界観と整合しているか精査し補正する。\n"
                            f"2. 【設定の整合性】既存設定全体と矛盾している点がないか確認し、矛盾があれば整合性を取る。\n"
                            f"3. 【解像度の向上】発動条件・コスト・リスク・視覚的イメージを具体化し、物語のフックとなる要素を加える。\n\n"
                            f"修正・ブラッシュアップが完了した最終的な設定案のみを出力してください。"
                        ),
                        expected_output="チェック済みの完成設定案", agent=checker
                    )
                    result = Crew(agents=[idea_generator, checker], tasks=[t1, t2], process=Process.sequential).kickoff()
                    st.session_state.current_draft = result.raw
                    
                    reply = f"{result.raw}\n\n---\n**💡 この設定をドキュメントに保存しますか？**\n（保存する場合は「はい」、修正する場合は指示を入力してください）"
                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})

            # 📖 モード2: 小説執筆モード
            else:
                history_text = "".join([f"【{'ユーザー' if msg['role']=='user' else 'AI'}】\n{msg['content']}\n\n" for msg in st.session_state.messages[-5:-1]])
                
                # Step 1: 小説家が本文ドラフトを執筆
                t1 = Task(
                    description=(
                        f"設定ドキュメント:\n{st.session_state.doc_content[:3000]}\n\n"
                        f"会話の流れ:\n{history_text}\n"
                        f"ユーザーの執筆指示:\n{user_input}\n\n"
                        f"上記の設定（特に『ソースの言語体系』に沿った名称・用語）と指示を遵守し、小説の本文（またはシーン・会話）を書き上げてください。"
                    ),
                    expected_output="小説本文の初稿ドラフト", agent=novel_writer
                )
                
                # Step 2: 推敲エージェントが文体や描写をブラッシュアップ
                t2 = Task(
                    description=(
                        f"設定ドキュメント:\n{st.session_state.doc_content[:3000]}\n\n"
                        f"小説家が書き上げた初稿ドラフトを受け取り、情景描写・感情表現・文体のリズム・会話のテンポ・言語体系に沿った用語表現を磨き上げ、魅力的な小説本文に完成させてください。"
                    ),
                    expected_output="推敲済みの小説本文", agent=prose_editor
                )
                
                result = Crew(agents=[novel_writer, prose_editor], tasks=[t1, t2], process=Process.sequential).kickoff()
                st.session_state.current_draft = result.raw
                
                reply = f"{result.raw}\n\n---\n**💡 この本文をドキュメントに保存しますか？**\n（保存する場合は「はい」、修正する場合は「もう少し会話を増やして」のように指示してください）"
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})