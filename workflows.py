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
            f"ユーザーの要望（アイデア出し、固有名称の変更・候補、要素のバリエーション出し等）に対し、**簡潔な候補リスト（5〜10パターン）**を提示してください。\n\n"
            f"【★絶対厳守のルール】\n"
            f"1. **絶対に詳細な単一設定フォーマット（概要・詳細メカニズム・歴史背景など）を出力しないでください。**\n"
            f"2. 各候補は番号付きリストで、1項目あたり1〜2行程度（名称＋簡単な特徴や選定理由）で簡潔に出力してください。\n"
            f"3. 固有名称や作中用語の提案が含まれる場合は、言語体系に基づき必ず以下の表記ルールを守ってください：\n"
            f"   `原語（英語訳）：日本語で○○という意味` （例: Kaiser（Emperor）：日本語で皇帝という意味。）\n"
            f"4. 王道から重厚、変則的な切り口までバリエーション豊かに並べてください。"
        ),
        expected_output="5〜10パターンの簡潔な候補リスト（Markdown形式）",
        agent=idea_generator
    )
    result = Crew(agents=[idea_generator], tasks=[task], process=Process.sequential).kickoff()
    return result.raw


# 3. 設定構築ワークフロー（1案の詳細化：3エージェント連動）
def run_setting_creation(agents, doc_content, history_text, user_input):
    idea_generator = agents["idea_generator"]
    tactics_supervisor = agents["tactics_supervisor"]
    checker = agents["checker"]
    
    tactics_tabs = get_tabs_by_keywords(doc_content, ["国家", "世界情勢", "宗教", "人族", "魔物", "魔法"])
    checker_tabs = get_tabs_by_keywords(doc_content, ["言語"])
    
    t1 = Task(
        description=(
            f"【既存設定ドキュメント（全設定）】\n{doc_content}\n\n"
            f"【会話の文脈】\n{history_text}\n"
            f"【ユーザー指示】\n{user_input}\n\n"
            f"【タスク】\n"
            f"上記の世界観と指示を踏まえ、選択されたアイデア・設定を詳細化し、具体的で魅力的な初期ドラフトを作成してください。\n"
            f"概要、詳細メカニズム、視覚・イメージ的特徴を含めて構成してください。"
        ),
        expected_output="設定案の初期ドラフト（概要・メカニズム・特徴）", 
        agent=idea_generator
    )
    
    t2 = Task(
        description=(
            f"【関連設定ドキュメント（国家・情勢・宗教・人族/魔物・魔法）】\n{tactics_tabs}\n\n"
            f"【タスク】\n"
            f"直前の初期ドラフトに対し、関連設定を踏まえて厳密なリアリティチェックと修正を行ってください：\n"
            f"1. 【地政学・政治】国家の経済基盤、領土・資源争い、為政者の動機に現実的な政治力学の整合性があるか。\n"
            f"2. 【軍略・兵站】戦闘・戦法・兵器が含まれる場合、地形、補給線、史実・戦史のロジックを取り入れているか。\n"
            f"3. 【リアリティ補強】知識層の読者が読んでも納得できるよう、背景にある「歴史的因果関係」を補強してください。"
        ),
        expected_output="歴史・地政学・軍略的ロジックが補強された設定ドラフト", 
        agent=tactics_supervisor,
        context=[t1]
    )
    
    t3 = Task(
        description=(
            f"【言語設定ドキュメント（言語体系）】\n{checker_tabs}\n\n"
            f"【タスク】\n"
            f"直前のドラフトを最終校閲し、言語体系および以下のルールとフォーマットを**厳格に適用して**完成版を出力してください：\n\n"
            f"【★言語表記の絶対ルール】\n"
            f"設定内に登場する作中用語や固有名詞、外国語単語には、**必ず日本語訳と英語訳をセットで記述**してください。\n"
            f"・ドイツ語単語の場合：`ドイツ語単語（英語訳）：日本語で○○という意味。`（例：Kaiser（Emperor）：日本語で皇帝という意味。）\n"
            f"・英語単語の場合：`英語単語（English）：日本語で○○という意味`\n"
            f"・その他の言語も同様に、`原語単語（英語訳）：日本語で○○という意味` の形式を統一してください。\n\n"
            f"【その他のチェック】\n"
            f"1. 『言語』タブの記述に沿い、語源・ニュアンスを正確に修整する。\n"
            f"2. 既存設定との重複や矛盾を排除する。\n\n"
            f"【出力フォーマット（必ずこの形式で出力してください）】\n"
            f"## ■ 設定名称（言語表記ルールに沿った名称）\n"
            f"**【概要】**（1〜2文で簡潔に）\n"
            f"**【詳細・メカニズム】**（具体的ルールや発動条件、コスト・リスク）\n"
            f"**【言語・用語解説】**（作中用語の「言語（英語訳）：日本語で〜の意味」を箇条書きで一覧表示）\n"
            f"**【歴史・地政学的背景】**（なぜその設定が存在・成立しているかのリアリティ）\n"
            f"**【物語への影響・フック】**（キャラや展開にどう絡むか）"
        ),
        expected_output="言語表記ルールを厳守した完成版設定案（Markdown形式）", 
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
            f"   ※用語解説を入れる場合は `ドイツ語（英語訳）：日本語で○○という意味` 等の形式を厳守すること。\n\n"
            f"※挨拶や解説は含めず、**小説の本文のみ**を出力してください。"
        ),
        expected_output="推敲済みの小説本文のみ（Markdown形式）", 
        agent=prose_editor,
        context=[t1]
    )
    
    result = Crew(agents=[novel_writer, prose_editor], tasks=[t1, t2], process=Process.sequential).kickoff()
    return result.raw