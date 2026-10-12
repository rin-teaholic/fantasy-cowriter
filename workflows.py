from crewai import Task, Crew, Process

# 1. 設定提案ワークフロー（ディレクター）
def run_setting_proposal(agents, doc_content):
    director = agents["director"]
    task = Task(
        description=(
            f"【既存設定ドキュメント】\n{doc_content[:3000]}...\n\n"
            f"【指示】\n"
            f"上記の設定を踏まえ、世界観をより深掘りするために次に詰めるべきテーマ案を5つ提案してください。\n"
            f"各テーマには「なぜ今その設定が必要か（物語や世界観への効果）」を1行で添えてください。"
        ), 
        expected_output="整理された5つのテーマ提案リスト（Markdown形式）", 
        agent=director
    )
    result = Crew(agents=[director], tasks=[task], process=Process.sequential).kickoff()
    return result.raw


# 2. 設定構築ワークフロー（3エージェント連動）
def run_setting_creation(agents, doc_content, history_text, user_input):
    idea_generator = agents["idea_generator"]
    tactics_supervisor = agents["tactics_supervisor"]
    checker = agents["checker"]
    
    # Step 1: アイデア出し
    t1 = Task(
        description=(
            f"【既存設定ドキュメント】\n{doc_content[:3000]}\n\n"
            f"【会話の文脈】\n{history_text}\n"
            f"【ユーザー指示】\n{user_input}\n\n"
            f"【タスク】\n"
            f"上記を踏まえ、具体的で魅力的・独創的な設定案の初期ドラフトを作成してください。\n"
            f"概要、詳細メカニズム、視覚・イメージ的特徴を含めて構成してください。"
        ),
        expected_output="設定案の初期ドラフト（概要・メカニズム・特徴）", 
        agent=idea_generator
    )
    
    # Step 2: 歴史・政治・地政学・軍略チェック
    t2 = Task(
        description=(
            f"【既存設定ドキュメント】\n{doc_content[:3000]}\n\n"
            f"【初期ドラフト】\n受け取ったドラフトに対し、以下の観点で厳密なリアリティチェックと修正を行ってください：\n"
            f"1. 【地政学・政治】国家の経済基盤、領土・資源争い、為政者の動機に現実的な政治力学の整合性があるか。\n"
            f"2. 【軍略・兵站】戦闘・戦法・兵器が含まれる場合、地形、補給線（兵站）、過去の史実・戦史（有名な逆転劇や戦略）のロジックを取り入れているか。\n"
            f"3. 【リアリティ補強】知識層の読者が読んでも納得できるよう、背景にある「歴史的因果関係」を補強してください。"
        ),
        expected_output="歴史・地政学・軍略的ロジックが補強された設定ドラフト", 
        agent=tactics_supervisor
    )
    
    # Step 3: 言語体系・ルール厳守・最終校閲
    t3 = Task(
        description=(
            f"【既存設定ドキュメント】\n{doc_content[:3000]}\n\n"
            f"【検証済みドラフト】\n受け取ったドラフトを最終校閲し、以下のルールとフォーマットを**厳格に適用して**完成版を出力してください：\n\n"
            f"【★言語表記の絶対ルール】\n"
            f"設定内に登場する作中用語や固有名詞、外国語単語については、**必ず日本語訳と英語訳をセットで記述**してください。\n"
            f"・ドイツ語単語の場合：`ドイツ語単語（英語訳）：日本語で○○という意味。`（例：Kaiser（Emperor）：日本語で皇帝という意味。）\n"
            f"・英語単語の場合：`英語単語（English）：日本語で○○という意味`（例：Knight（Knight）：日本語で騎士という意味。）\n"
            f"・その他の言語も同様に、`原語単語（英語訳）：日本語で○○という意味` の形式を統一してください。\n\n"
            f"【その他のチェック】\n"
            f"1. ドキュメント内の『ソースの言語体系』の記述に沿い、語源・ニュアンスを正確に修整する。\n"
            f"2. 既存設定との矛盾を完全に解消する。\n\n"
            f"【出力フォーマット（必ずこの形式で出力してください）】\n"
            f"## ■ 設定名称（言語表記ルールに沿った名称）\n"
            f"**【概要】**（1〜2文で簡潔に）\n"
            f"**【詳細・メカニズム】**（具体的ルールや発動条件、コスト・リスク）\n"
            f"**【言語・用語解説】**（作中用語の「言語（英語訳）：日本語で〜の意味」を箇条書きで一覧表示）\n"
            f"**【歴史・地政学的背景】**（なぜその設定が存在・成立しているかのリアリティ）\n"
            f"**【物語への影響・フック】**（キャラや展開にどう絡むか）"
        ),
        expected_output="言語表記ルールを厳守した完成版設定案（Markdown形式）", 
        agent=checker
    )
    
    result = Crew(agents=[idea_generator, tactics_supervisor, checker], tasks=[t1, t2, t3], process=Process.sequential).kickoff()
    return result.raw


# 3. 小説執筆ワークフロー（2エージェント連動）
def run_novel_writing(agents, doc_content, history_text, user_input):
    novel_writer = agents["novel_writer"]
    prose_editor = agents["prose_editor"]
    
    t1 = Task(
        description=(
            f"【設定ドキュメント】\n{doc_content[:3000]}\n\n"
            f"【会話の文脈】\n{history_text}\n"
            f"【執筆指示】\n{user_input}\n\n"
            f"【タスク】\n"
            f"設定（特に『ソースの言語体系』や地政学的背景）を正しく反映し、指定されたシーンの本文を執筆してください。\n"
            f"登場人物の心情、台詞回し、五感に訴える描写を意識してください。"
        ),
        expected_output="小説本文の初稿ドラフト", 
        agent=novel_writer
    )
    
    t2 = Task(
        description=(
            f"【初稿ドラフト】\n受け取った本文を推敲・ブラッシュアップし、文芸作品として高品質な完成原稿に仕上げてください。\n\n"
            f"【推敲基準】\n"
            f"1. 文体のリズムと地の文・会話文のバランス調整\n"
            f"2. 五感（視覚・聴覚・匂い・空気感）描写の強化\n"
            f"3. キャラクターの感情変化の機微とテンポ感の最適化\n"
            f"4. 『ソースの言語体系』に沿った固有名詞・用語の表記チェック。\n"
            f"   ※作中用語や解説を入れる場合は、必ず `ドイツ語（英語訳）：日本語で○○という意味` や `英語（English）：日本語で○○という意味` の形式を徹底してください。\n\n"
            f"※挨拶や解説は含めず、**小説の本文のみ**を出力してください。"
        ),
        expected_output="推敲済みの小説本文のみ（Markdown形式）", 
        agent=prose_editor
    )
    
    result = Crew(agents=[novel_writer, prose_editor], tasks=[t1, t2], process=Process.sequential).kickoff()
    return result.raw