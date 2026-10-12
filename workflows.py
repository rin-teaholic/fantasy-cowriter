from crewai import Task, Crew, Process

def run_setting_proposal(agents, doc_content):
    director = agents["director"]
    task = Task(
        description=f"以下の既存設定を踏まえ、次に設定を詰めるべきテーマ案を5つ提案して。\n\n{doc_content[:3000]}...", 
        expected_output="テーマの選択肢", 
        agent=director
    )
    result = Crew(agents=[director], tasks=[task], process=Process.sequential).kickoff()
    return result.raw

def run_setting_creation(agents, doc_content, history_text, user_input):
    idea_generator = agents["idea_generator"]
    tactics_supervisor = agents["tactics_supervisor"]
    checker = agents["checker"]
    
    t1 = Task(
        description=f"既存設定:\n{doc_content[:3000]}\n\n会話の流れ:\n{history_text}\n最新指示:\n{user_input}\n\n具体的で魅力的な設定案の初期ドラフトを作成してください。",
        expected_output="設定案の初期ドラフト", agent=idea_generator
    )
    t2 = Task(
        description=(
            f"既存設定:\n{doc_content[:3000]}\n\n"
            f"初期ドラフトを受け取り、以下の基準で検証・修正してください：\n"
            f"1. 【政治・地政学のリアリティ】国家の成り立ち、資源や領土を巡る対立、為政者の判断が、現実の歴史や地政学の観点から見て不自然・ご都合主義になっていないか。\n"
            f"2. 【軍略・戦術の説得力】戦闘や危機的状況のシナリオが含まれる場合、地形や兵站、現実の戦史のロジックを取り入れ、知識層が読んでも納得する展開に深化させる。\n\n"
            f"歴史的・軍事的に説得力を持たせたドラフトを出力してください。"
        ),
        expected_output="歴史・軍略的チェックを経た設定案", agent=tactics_supervisor
    )
    t3 = Task(
        description=(
            f"既存設定:\n{doc_content[:3000]}\n\n"
            f"軍略チェックを経たドラフトを受け取り、以下の基準で最終チェックおよび修正を行ってください：\n"
            f"1. 【言語体系・表現チェック】既存設定にある『ソースの言語体系』の記述を基準とし、国ごとの使用言語、単語のニュアンス、固有名詞の綴り・響きが世界観と整合しているか精査し補正する。\n"
            f"2. 【設定の整合性】既存設定全体と矛盾している点がないか確認し、矛盾があれば整合性を取る。\n"
            f"3. 【解像度の向上】表現をより具体化し、物語のフックとなる要素を加える。\n\n"
            f"修正・ブラッシュアップが完了した最終的な設定案のみを出力してください。"
        ),
        expected_output="チェック済みの完成設定案", agent=checker
    )
    
    result = Crew(agents=[idea_generator, tactics_supervisor, checker], tasks=[t1, t2, t3], process=Process.sequential).kickoff()
    return result.raw

def run_novel_writing(agents, doc_content, history_text, user_input):
    novel_writer = agents["novel_writer"]
    prose_editor = agents["prose_editor"]
    
    t1 = Task(
        description=(
            f"設定ドキュメント:\n{doc_content[:3000]}\n\n"
            f"会話の流れ:\n{history_text}\n"
            f"ユーザーの執筆指示:\n{user_input}\n\n"
            f"上記の設定（特に『ソースの言語体系』に沿った名称・用語）と指示を遵守し、小説の本文（またはシーン・会話）を書き上げてください。"
        ),
        expected_output="小説本文の初稿ドラフト", agent=novel_writer
    )
    
    t2 = Task(
        description=(
            f"設定ドキュメント:\n{doc_content[:3000]}\n\n"
            f"小説家が書き上げた初稿ドラフトを受け取り、情景描写・感情表現・文体のリズム・会話のテンポ・言語体系に沿った用語表現を磨き上げ、魅力的な小説本文に完成させてください。"
        ),
        expected_output="推敲済みの小説本文", agent=prose_editor
    )
    
    result = Crew(agents=[novel_writer, prose_editor], tasks=[t1, t2], process=Process.sequential).kickoff()
    return result.raw