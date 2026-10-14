import re
from crewai import Task, Crew, Process

# --- タブ抽出用ヘルパー関数 ---
def extract_tab_sections(doc_content: str) -> dict[str, str]:
    pattern = r'(?m)^(?:={3,}|-{3,}|#{1,3}|■|【|\[)\s*(?:タブ[:：]\s*)?([^\n=―\-】\]#]+?)(?:\s*={3,}|\s*-{3,}|】|\])?$'
    splits = re.split(pattern, doc_content)
    
    if len(splits) <= 1:
        return {"all": doc_content}
    
    tabs = {}
    if splits[0].strip():
        tabs["概要"] = splits[0].strip()
        
    for i in range(1, len(splits), 2):
        tab_name = splits[i].strip()
        tab_text = splits[i+1].strip() if i+1 < len(splits) else ""
        tabs[tab_name] = tab_text
        
    return tabs

def get_tabs_by_keywords(doc_content: str, keywords: list[str]) -> str:
    tabs = extract_tab_sections(doc_content)
    matched = []
    for tab_name, text in tabs.items():
        if any(kw.lower() in tab_name.lower() for kw in keywords):
            matched.append(f"### 【タブ: {tab_name}】\n{text}")
    
    if not matched:
        return doc_content
    return "\n\n".join(matched)


# 1. 設定提案ワークフロー（ディレクター）
def run_setting_proposal(agents, doc_content):
    director = agents["director"]
    task = Task(
        description=(
            f"【既存設定ドキュメント】\n{doc_content}\n\n"
            f"【指示】\n"
            f"上記の設定を踏まえ、世界観をより深掘りするために次に詰めるべきテーマ案を5つ提案してください。\n"
            f"各テーマには「なぜ今その設定が必要か（物語や世界観への効果）」を1行で添えてください。"
        ), 
        expected_output="整理された5つのテーマ提案リスト（Markdown形式）", 
        agent=director
    )
    result = Crew(agents=[director], tasks=[task], process=Process.sequential).kickoff()
    return result.raw


# 2. 候補出し・ブレストワークフロー（多パターン・名称候補を1〜2行で一覧化）
def run_setting_brainstorm(agents, doc_content, history_text, user_input):
    idea_generator = agents["idea_generator"]
    checker_tabs = get_tabs_by_keywords(doc_content, ["言語"])
    
    task = Task(
        description=(
            f"【既存設定ドキュメント】\n{doc_content}\n\n"
            f"【言語体系（命名・表記ルール）】\n{checker_tabs}\n\n"
            f"【会話の文脈】\n{history_text}\n"
            f"【ユーザー指示】\n{user_input}\n\n"
            f"【タスク】\n"
            f"ユーザーの要望に対し、**簡潔な候補リスト（5〜10パターン）**を提示してください。\n\n"
            f"【★絶対厳守のルール】\n"
            f"1. **絶対に詳細な単一設定フォーマットを出力しないでください。**\n"
            f"2. 各候補は番号付きリストで、1項目あたり1〜2行程度（名称＋簡単な特徴や選定理由）で簡潔に出力してください。\n"
            f"3. 固有名称や作中用語の提案が含まれる場合は、言語体系に基づき必ず表記ルールを守ってください：\n"
            f"   `原語（英語訳）：日本語で○○という意味`\n"
            f"4. バリエーション豊かに並べてください。"
        ),
        expected_output="5〜10パターンの簡潔な候補リスト（Markdown形式）",
        agent=idea_generator
    )
    result = Crew(agents=[idea_generator], tasks=[task], process=Process.sequential).kickoff()
    return result.raw


# 3. 設定構築ワークフロー（柔軟な詳細化・キャラクター/制度両対応）
def run_setting_creation(agents, doc_content, history_text, user_input):
    idea_generator = agents["idea_generator"]
    tactics_supervisor = agents["tactics_supervisor"]
    checker = agents["checker"]
    
    tactics_tabs = get_tabs_by_keywords(doc_content, ["国家", "世界情勢", "宗教", "人族", "魔物", "魔法"])
    checker_tabs = get_tabs_by_keywords(doc_content, ["言語"])
    
    # Step 1: アイデア・設定の具現化
    t1 = Task(
        description=(
            f"【既存設定ドキュメント】\n{doc_content}\n\n"
            f"【会話の文脈】\n{history_text}\n"
            f"【ユーザー指示】\n{user_input}\n\n"
            f"【タスク】\n"
            f"会話の文脈とユーザーの指示を正確に汲み取り、指定された設定（キャラクターの口調・性格、あるいは魔法・国家・組織等）を具体化してください。\n"
            f"ユーザーが前回の提案（例：1番）に特定の要素（例：優しさ）を加えるよう指示している場合は、そのニュアンスを的確に融合させたドラフトを作成してください。"
        ),
        expected_output="ユーザー指示を的確に反映した設定ドラフト", 
        agent=idea_generator
    )
    
    # Step 2: リアリティ・心理・世界観の整合性チェック
    t2 = Task(
        description=(
            f"【関連設定ドキュメント】\n{tactics_tabs}\n\n"
            f"【タスク】\n"
            f"直前のドラフトを精査し、世界観との整合性を補強してください：\n"
            f"・【キャラクター/口調設定の場合】その人物の境遇、家族関係（弟・父・母・リリー）、世界観の過酷さや将来の運命を踏まえ、心理描写や言葉遣いに説得力を持たせる。\n"
            f"・【国家/軍事/魔法設定の場合】地政学、軍略、補給線、歴史的因果関係に矛盾がないか検証する。"
        ),
        expected_output="説得力と深みが補強された設定ドラフト", 
        agent=tactics_supervisor,
        context=[t1]
    )
    
    # Step 3: 最適なフォーマットの適用と最終校閲
    t3 = Task(
        description=(
            f"【言語設定ドキュメント】\n{checker_tabs}\n\n"
            f"【タスク】\n"
            f"直前のドラフトを最終校閲し、**設定の種類に応じた最適なフォーマット**で完成版を出力してください。\n\n"
            f"【フォーマットの分岐ルール（厳守）】\n"
            f"■ パターンA：【キャラクターの口調・性格・台詞設定の場合】\n"
            f"## ■ キャラクター名・口調設定名称\n"
            f"**【口調・性格の基本コンセプト】**（全体の雰囲気、ベースとなった要素）\n"
            f"**【一人称・二人称・呼び方】**（自分、両親、弟、幼馴染など）\n"
            f"**【話し方の特徴・ルール】**（語尾、声のトーン、感情表現の癖）\n"
            f"**【シチュエーション別・台詞サンプル】**\n"
            f"- 日常・家族との会話（例：〜）\n"
            f"- 弟（ブレイク）への接し方（例：〜）\n"
            f"- 幼馴染（リリー）への接し方（例：〜）\n"
            f"- 感情が高ぶった時・シリアス（例：〜）\n"
            f"**【内面・物語への影響】**（過酷な世界やループ運命とどう響き合うか）\n\n"
            f"■ パターンB：【世界観・国家・魔法・制度・兵器設定の場合】\n"
            f"## ■ 設定名称（言語表記ルールに沿った名称）\n"
            f"**【概要】**\n"
            f"**【詳細・メカニズム】**\n"
            f"**【言語・用語解説】**（作中用語があれば `原語（英語訳）：日本語で〜の意味` の形式を厳守）\n"
            f"**【歴史・地政学的背景】**\n"
            f"**【物語への影響・フック】**"
        ),
        expected_output="設定種別に適合した完成版設定案（Markdown形式）", 
        agent=checker,
        context=[t2]
    )
    
    result = Crew(agents=[idea_generator, tactics_supervisor, checker], tasks=[t1, t2, t3], process=Process.sequential).kickoff()
    return result.raw


# 4. 小説執筆ワークフロー（2エージェント連動）
def run_novel_writing(agents, doc_content, history_text, user_input):
    novel_writer = agents["novel_writer"]
    prose_editor = agents["prose_editor"]
    checker_tabs = get_tabs_by_keywords(doc_content, ["言語"])
    
    t1 = Task(
        description=(
            f"【設定ドキュメント】\n{doc_content}\n\n"
            f"【会話の文脈】\n{history_text}\n"
            f"【執筆指示】\n{user_input}\n\n"
            f"【タスク】\n"
            f"設定を正しく反映し、指定されたシーンの本文を執筆してください。\n"
            f"登場人物の心情、台詞回し、五感に訴える描写を意識してください。"
        ),
        expected_output="小説本文の初稿ドラフト", 
        agent=novel_writer
    )
    
    t2 = Task(
        description=(
            f"【言語設定ドキュメント】\n{checker_tabs}\n\n"
            f"【推敲指示】\n"
            f"直前の初稿ドラフトを受け取り、文芸作品として高品質な完成原稿に仕上げてください。\n\n"
            f"【推敲基準】\n"
            f"1. 文体のリズムと地の文・会話文のバランス調整\n"
            f"2. 五感描写の強化\n"
            f"3. 感情変化の機微とテンポ感の最適化\n"
            f"4. 『言語』タブの規則に沿った固有名詞表記チェック。\n"
            f"※挨拶や解説は含めず、**小説の本文のみ**を出力してください。"
        ),
        expected_output="推敲済みの小説本文のみ（Markdown形式）", 
        agent=prose_editor,
        context=[t1]
    )
    
    result = Crew(agents=[novel_writer, prose_editor], tasks=[t1, t2], process=Process.sequential).kickoff()
    return result.raw