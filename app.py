import os
import streamlit as st
import streamlit.components.v1 as components
from crewai import Task, Crew, Process
from auth import check_password
from agents import get_agents
from workflows import (
    run_setting_proposal,
    run_setting_brainstorm,
    run_setting_creation,
    run_novel_writing,
)
from tools.gdocs_tool import ReadGoogleDocTool, AppendGoogleDocTool

# --- 画面の基本設定 ---
st.set_page_config(page_title="Fantasy Co-Writer", page_icon="✍️", layout="centered")

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

if not check_password():
    st.stop()

os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
DOCUMENT_ID = st.secrets["DOCUMENT_ID"]

PRIMARY_MODEL = "gemini/gemini-3.5-flash-lite"
FALLBACK_MODEL = "gemini/gemini-3.1-flash-lite"

@st.cache_resource
def init_tools():
    return ReadGoogleDocTool(), AppendGoogleDocTool()

@st.cache_resource
def get_agent_pool(model_name):
    return get_agents(model_name)

read_tool, append_tool = init_tools()
primary_agents = get_agent_pool(PRIMARY_MODEL)
fallback_agents = get_agent_pool(FALLBACK_MODEL)

def run_with_fallback(workflow_func, *args):
    try:
        return workflow_func(primary_agents, *args), False
    except Exception as e:
        print(f"⚠️ [LOG] プライマリモデル失敗: {e} -> 予備モデルで再試行します")
        try:
            return workflow_func(fallback_agents, *args), True
        except Exception as fallback_error:
            print(f"❌ [LOG] 予備モデルも失敗: {fallback_error}")
            raise RuntimeError(f"両モデルでリクエストが失敗しました: {fallback_error}")

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

if not st.session_state.doc_content:
    with st.spinner("Googleドキュメントを読み込み中..."):
        try:
            st.session_state.doc_content = read_tool._run(document_id=DOCUMENT_ID)
        except Exception as e:
            st.error(f"ドキュメントの読み込みに失敗しました: {e}")

st.title("✍️ Fantasy Co-Writer")

# ==========================================
# 1. モード未選択時：タップ選択画面
# ==========================================
if st.session_state.selected_mode is None:
    st.write("### どちらの作業を行いますか？ タップして選択してください")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🛠️ 設定構築モード\n\n(世界観・国家・魔法・言語の作成)", use_container_width=True):
            st.session_state.selected_mode = "🛠️ 設定構築モード"
            with st.spinner("ディレクターが設定ドキュメントを読み込み、提案を準備中..."):
                try:
                    proposal, used_fallback = run_with_fallback(run_setting_proposal, st.session_state.doc_content)
                    fallback_notice = "\n\n*(※メインモデル混雑のため予備モデルで提案を生成しました)*" if used_fallback else ""
                    initial_msg = (
                        "👋 **ディレクターです！設定構築モードを開始します。**\n\n"
                        "既存のドキュメントを踏まえ、次に深掘りすべきテーマ案をまとめました：\n\n"
                        f"{proposal}{fallback_notice}\n\n---\n"
                        "💡 **使い方:**\n"
                        "- 「〇〇のアイデアを出して」「この名称を変更したい。いくつか提案して」➔ 簡潔な候補リストを提示します\n"
                        "- 気になる候補があれば「○番で詳細化して」➔ 地政学・言語ルールを適用した完全版設定を作成します"
                    )
                except Exception:
                    initial_msg = "⚠️ APIが極度に混雑しています。数十秒待ってから「🔄 モード切替」を押して再試行してください。"
                
                st.session_state.messages.append({"role": "assistant", "content": initial_msg})
            st.rerun()

    with col2:
        if st.button("📖 小説執筆モード\n\n(本文・シーン・対話の執筆)", use_container_width=True):
            st.session_state.selected_mode = "📖 小説執筆モード"
            with st.spinner("ディレクターが執筆の切り口を準備中..."):
                try:
                    def novel_init(agents_map):
                        director = agents_map["director"]
                        task = Task(
                            description=(
                                f"【既存設定】\n{st.session_state.doc_content}...\n\n"
                                f"上記の設定を踏まえ、小説本文の執筆を開始するにあたって、おすすめのシーンやエピソードの切り口を3〜4つ提案してください。"
                            ),
                            expected_output="シーン・エピソードの候補リスト",
                            agent=director
                        )
                        return Crew(agents=[director], tasks=[task], process=Process.sequential).kickoff().raw
                    
                    result_raw, used_fallback = run_with_fallback(novel_init)
                    fallback_notice = "\n\n*(※メインモデル混雑のため予備モデルで生成しました)*" if used_fallback else ""
                    initial_msg = (
                        "👋 **ディレクターです！小説執筆モードを開始します。**\n\n"
                        "既存の世界観・設定をベースに、執筆を始めるおすすめのシーンをいくつかピックアップしました：\n\n"
                        f"{result_raw}{fallback_notice}\n\n---\n"
                        "書きたいシーンや指示を入力してください！"
                    )
                except Exception:
                    initial_msg = "⚠️ APIが極度に混雑しています。数十秒待ってから「🔄 モード切替」を押して再試行してください。"
                
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

# チャット履歴の表示（デバッグ情報表示付き）
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        # デバッグログが保存されている場合、折りたたみで画面上に表示
        if msg.get("debug_info"):
            with st.expander("🔍 送信ログ・文脈を確認"):
                st.markdown("**【ユーザー指示】**")
                st.text(msg["debug_info"].get("input", ""))
                st.markdown("**【AIに渡した過去の文脈 (history_text)】**")
                st.text(msg["debug_info"].get("history", "(なし)"))
                st.markdown("**【実行されたパイプライン】**")
                st.code(msg["debug_info"].get("pipeline", "不明"))

# --- AI返答処理 ---
if st.session_state.generating_response:
    with st.chat_message("assistant"):
        with st.spinner("AIチームが作業中..."):
            user_input = st.session_state.messages[-1]["content"]
            history_text = "".join([f"【{'ユーザー' if msg['role']=='user' else 'AI'}】\n{msg['content']}\n\n" for msg in st.session_state.messages[-5:-1]])
            
            # ターミナルログ出力
            print("\n" + "="*50)
            print(f"📩 [USER INPUT]: {user_input}")
            print(f"📜 [HISTORY TEXT]:\n{history_text}")
            print("="*50 + "\n")

            debug_pipeline_name = "未判定"
            
            try:
                # 【共通処理】保存指示の場合
                if user_input.lower() in ['y', 'ok', 'はい', '保存', '保存して']:
                    debug_pipeline_name = "保存処理"
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
                    if user_input.strip() in ["提案", "テーマ提案", "次何する？"]:
                        debug_pipeline_name = "run_setting_proposal（テーマ再提案）"
                        raw_result, used_fallback = run_with_fallback(run_setting_proposal, st.session_state.doc_content)
                        notice = " *(※予備モデルで回答)*" if used_fallback else ""
                        reply = f"【ディレクターからの提案】{notice}\n{raw_result}"
                    
                    else:
                        is_detail_request = any(kw in user_input for kw in ["詳細化", "詳しく", "深掘り", "決定", "これにする", "確定", "詰めて", "具体化", "作成して", "完成させて"])
                        is_brainstorm_request = any(kw in user_input for kw in [
                            "パターン", "アイディア", "アイデア", "候補", "ブレスト",
                            "いくつか", "複数", "何個か", "別案", "別の", "違う", "変更",
                            "名称", "名前", "ネーミング", "言い換え", "バリエーション",
                            "リスト", "10", "5", "案を", "案出", "提案"
                        ])
                        
                        # 候補出し判定
                        if is_brainstorm_request and not is_detail_request:
                            debug_pipeline_name = "run_setting_brainstorm（候補・ブレスト出し）"
                            raw_result, used_fallback = run_with_fallback(run_setting_brainstorm, st.session_state.doc_content, history_text, user_input)
                            notice = "\n\n*(※予備モデルで生成)*" if used_fallback else ""
                            reply = f"{raw_result}{notice}\n\n---\n**💡 気になる候補はありますか？**\n（例：『3番で詳細化して』『2番の名称を採用して設定を詰めて』のように指定してください）"
                        
                        # 1案の詳細作成パイプライン
                        else:
                            debug_pipeline_name = "run_setting_creation（詳細化パイプライン）"
                            raw_result, used_fallback = run_with_fallback(run_setting_creation, st.session_state.doc_content, history_text, user_input)
                            st.session_state.current_draft = raw_result
                            notice = "\n\n*(※予備モデルで生成)*" if used_fallback else ""
                            reply = f"{raw_result}{notice}\n\n---\n**💡 この設定をドキュメントに保存しますか？**\n（保存する場合は「はい」、修正する場合は指示を入力してください）"

                # 📖 小説執筆モード
                else:
                    debug_pipeline_name = "run_novel_writing（小説本文執筆）"
                    raw_result, used_fallback = run_with_fallback(run_novel_writing, st.session_state.doc_content, history_text, user_input)
                    st.session_state.current_draft = raw_result
                    notice = "\n\n*(※予備モデルで生成)*" if used_fallback else ""
                    reply = f"{raw_result}{notice}\n\n---\n**💡 この本文をドキュメントに保存しますか？**\n（保存する場合は「はい」、修正する場合は「もう少し描写を増やして」のように指示してください）"

                print(f"🤖 [RAW RESPONSE]:\n{raw_result if 'raw_result' in locals() else reply}\n")

            except Exception as e:
                print(f"❌ [ERROR]: {e}")
                reply = (
                    "⚠️ **Gemini API の極度なアクセス集中が発生しました。**\n\n"
                    "メインモデル・予備モデルの両方で一時的に制限がかかりました。\n"
                    "1分ほど時間を置いてから、もう一度送信してみてください。"
                )

            st.markdown(reply)
            
            # デバッグ情報を紐付けてメッセージ保存
            st.session_state.messages.append({
                "role": "assistant",
                "content": reply,
                "debug_info": {
                    "input": user_input,
                    "history": history_text,
                    "pipeline": debug_pipeline_name
                }
            })
            
            st.session_state.generating_response = False
            scroll_to_bottom()
            st.rerun()

# --- ユーザー入力エリア ---
with st.form(key="chat_form", clear_on_submit=True):
    user_input_raw = st.text_area(
        label="メッセージ入力",
        placeholder="メッセージを入力してください（例：『この名称を変更したい。いくつか提案して』『3番で詳細化して』）",
        height=100,
        label_visibility="collapsed"
    )
    submit_btn = st.form_submit_button("📤 送信", type="primary", use_container_width=True)

if submit_btn and user_input_raw.strip():
    user_input = user_input_raw.strip()
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.generating_response = True
    scroll_to_bottom()
    st.rerun()