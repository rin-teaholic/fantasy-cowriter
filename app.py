import os
import json
import uuid
import streamlit as st
import streamlit.components.v1 as components
from crewai import Task, Crew, Process
from auth import check_password, logout
from agents import get_agents
from workflows import (
    run_setting_proposal,
    run_setting_brainstorm,
    run_setting_creation,
    run_novel_writing,
)
from tools.gdocs_tool import ReadGoogleDocTool, AppendGoogleDocTool
from streamlit_cookies_controller import CookieController

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

# --- パスワード認証 (Cookie対応) ---
if not check_password():
    st.stop()

# --- セッション永続化マネージャー ---
controller = CookieController()
SESSION_COOKIE = "fc_session_id"
SESSIONS_DIR = ".sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

def get_or_create_session_id():
    sid = controller.get(SESSION_COOKIE)
    if not sid:
        sid = str(uuid.uuid4())
        controller.set(SESSION_COOKIE, sid)
    return sid

session_id = get_or_create_session_id()
session_file_path = os.path.join(SESSIONS_DIR, f"{session_id}.json")

def load_saved_session():
    if os.path.exists(session_file_path):
        try:
            with open(session_file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_current_session():
    data = {
        "selected_mode": st.session_state.selected_mode,
        "messages": st.session_state.messages,
        "current_draft": st.session_state.current_draft,
    }
    with open(session_file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- 環境変数とモデル設定 ---
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
        print(f"⚠️ [LOG] プライマリモデル失敗: {e} -> 予備モデルで再試行")
        try:
            return workflow_func(fallback_agents, *args), True
        except Exception as fallback_error:
            raise RuntimeError(f"両モデルでリクエストが失敗しました: {fallback_error}")

# --- セッション状態の復元・初期化 ---
persisted_data = load_saved_session()

if "selected_mode" not in st.session_state:
    st.session_state.selected_mode = persisted_data.get("selected_mode", None)
if "messages" not in st.session_state:
    st.session_state.messages = persisted_data.get("messages", [])
if "doc_content" not in st.session_state:
    st.session_state.doc_content = ""
if "current_draft" not in st.session_state:
    st.session_state.current_draft = persisted_data.get("current_draft", "")
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
            with st.spinner("ディレクターが提案を準備中..."):
                try:
                    proposal, used_fallback = run_with_fallback(run_setting_proposal, st.session_state.doc_content)
                    fallback_notice = "\n\n*(※予備モデルで生成)*" if used_fallback else ""
                    initial_msg = (
                        "👋 **ディレクターです！設定構築モードを開始します。**\n\n"
                        "既存のドキュメントを踏まえ、次に深掘りすべきテーマ案をまとめました：\n\n"
                        f"{proposal}{fallback_notice}\n\n---\n"
                        "💡 **使い方:**\n"
                        "- 「〇〇のアイデアを出して」➔ 候補リストを提示します\n"
                        "- 「○番に〜を足して整えて」➔ 完成版設定を作成します"
                    )
                except Exception:
                    initial_msg = "⚠️ API混雑中。時間を置いて「🔄 モード切替」を押してください。"
                
                st.session_state.messages.append({"role": "assistant", "content": initial_msg})
                save_current_session()
            st.rerun()

    with col2:
        if st.button("📖 小説執筆モード\n\n(本文・シーン・対話の執筆)", use_container_width=True):
            st.session_state.selected_mode = "📖 小説執筆モード"
            with st.spinner("ディレクターが執筆の切り口を準備中..."):
                try:
                    def novel_init(agents_map):
                        director = agents_map["director"]
                        task = Task(
                            description=f"【既存設定】\n{st.session_state.doc_content}...\n\n小説本文の執筆におすすめのシーンを3〜4つ提案してください。",
                            expected_output="シーン・エピソードの候補リスト",
                            agent=director
                        )
                        return Crew(agents=[director], tasks=[task], process=Process.sequential).kickoff().raw
                    
                    result_raw, used_fallback = run_with_fallback(novel_init)
                    fallback_notice = "\n\n*(※予備モデルで生成)*" if used_fallback else ""
                    initial_msg = (
                        "👋 **ディレクターです！小説執筆モードを開始します。**\n\n"
                        f"{result_raw}{fallback_notice}\n\n---\n"
                        "書きたいシーンや指示を入力してください！"
                    )
                except Exception:
                    initial_msg = "⚠️ API混雑中。時間を置いて再試行してください。"
                
                st.session_state.messages.append({"role": "assistant", "content": initial_msg})
                save_current_session()
            st.rerun()

    st.stop()

# ==========================================
# 2. モード選択後：チャット画面
# ==========================================
mode_col, update_col, reset_col, logout_col = st.columns([3, 2, 2, 1])
with mode_col:
    st.info(f"**モード:** {st.session_state.selected_mode}")

with update_col:
    if st.button("📄 最新化", help="Googleドキュメントを再読み込み", use_container_width=True):
        with st.spinner("更新中..."):
            try:
                st.session_state.doc_content = read_tool._run(document_id=DOCUMENT_ID)
                st.toast("✅ ドキュメントを更新しました！")
            except Exception as e:
                st.error(f"更新失敗: {e}")

with reset_col:
    if st.button("🔄 切替", help="モード選択に戻る", use_container_width=True):
        st.session_state.selected_mode = None
        st.session_state.messages = []
        st.session_state.current_draft = ""
        st.session_state.generating_response = False
        save_current_session()
        st.rerun()

with logout_col:
    if st.button("🚪", help="ログアウト"):
        logout()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("debug_info"):
            with st.expander("🔍 送信ログ・文脈を確認"):
                st.markdown("**【ユーザー指示】**")
                st.text(msg["debug_info"].get("input", ""))
                st.markdown("**【AIに渡した過去の文脈】**")
                st.text(msg["debug_info"].get("history", "(なし)"))
                st.markdown("**【実行パイプライン】**")
                st.code(msg["debug_info"].get("pipeline", "不明"))

# --- AI返答処理 ---
if st.session_state.generating_response:
    with st.chat_message("assistant"):
        with st.spinner("AIチームが作業中..."):
            user_input = st.session_state.messages[-1]["content"]
            history_text = "".join([f"【{'ユーザー' if msg['role']=='user' else 'AI'}】\n{msg['content']}\n\n" for msg in st.session_state.messages[-5:-1]])
            debug_pipeline_name = "未判定"
            
            try:
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

                elif "設定" in st.session_state.selected_mode:
                    if user_input.strip() in ["提案", "テーマ提案", "次何する？"]:
                        debug_pipeline_name = "run_setting_proposal（テーマ再提案）"
                        raw_result, used_fallback = run_with_fallback(run_setting_proposal, st.session_state.doc_content)
                        reply = f"【ディレクターからの提案】\n{raw_result}"
                    else:
                        is_brainstorm_request = any(kw in user_input for kw in [
                            "パターン", "アイディア", "アイデア", "候補", "ブレスト",
                            "いくつか", "複数", "何個か", "別案", "別の", "違う候補",
                            "名前の候補", "名称の候補", "ネーミング案", "バリエーション",
                            "リストアップ", "10個", "5個", "案を出して", "案出", "軽く出して"
                        ])
                        
                        if is_brainstorm_request:
                            debug_pipeline_name = "run_setting_brainstorm（候補・ブレスト出し）"
                            raw_result, used_fallback = run_with_fallback(run_setting_brainstorm, st.session_state.doc_content, history_text, user_input)
                            notice = "\n\n*(※予備モデルで生成)*" if used_fallback else ""
                            reply = f"{raw_result}{notice}\n\n---\n**💡 気になる候補はありますか？**\n（例：『1番に〜を足して整えて』のように指定してください）"
                        else:
                            debug_pipeline_name = "run_setting_creation（詳細化・台詞/設定作成）"
                            raw_result, used_fallback = run_with_fallback(run_setting_creation, st.session_state.doc_content, history_text, user_input)
                            st.session_state.current_draft = raw_result
                            notice = "\n\n*(※予備モデルで生成)*" if used_fallback else ""
                            reply = f"{raw_result}{notice}\n\n---\n**💡 この設定をドキュメントに保存しますか？**\n（保存する場合は「はい」、修正する場合は指示を入力してください）"

                else:
                    debug_pipeline_name = "run_novel_writing（小説本文執筆）"
                    raw_result, used_fallback = run_with_fallback(run_novel_writing, st.session_state.doc_content, history_text, user_input)
                    st.session_state.current_draft = raw_result
                    notice = "\n\n*(※予備モデルで生成)*" if used_fallback else ""
                    reply = f"{raw_result}{notice}\n\n---\n**💡 この本文をドキュメントに保存しますか？**\n（保存する場合は「はい」、修正する場合は指示を入力してください）"

            except Exception as e:
                reply = "⚠️ API混雑が発生しました。数十秒待ってから再試行してください。"

            st.markdown(reply)
            st.session_state.messages.append({
                "role": "assistant",
                "content": reply,
                "debug_info": {
                    "input": user_input,
                    "history": history_text,
                    "pipeline": debug_pipeline_name
                }
            })
            save_current_session()
            st.session_state.generating_response = False
            scroll_to_bottom()
            st.rerun()

# --- ユーザー入力エリア ---
with st.form(key="chat_form", clear_on_submit=True):
    user_input_raw = st.text_area(
        label="メッセージ入力",
        placeholder="メッセージを入力してください",
        height=100,
        label_visibility="collapsed"
    )
    submit_btn = st.form_submit_button("📤 送信", type="primary", use_container_width=True)

if submit_btn and user_input_raw.strip():
    user_input = user_input_raw.strip()
    st.session_state.messages.append({"role": "user", "content": user_input})
    save_current_session()
    st.session_state.generating_response = True
    scroll_to_bottom()
    st.rerun()