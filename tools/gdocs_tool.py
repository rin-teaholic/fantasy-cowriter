import os.path
import json
import streamlit as st
from typing import Type, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/documents']

def get_gdocs_service():
    # StreamlitのSecretsからJSON文字列を読み込み、辞書型に変換
    creds_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
    # ファイルからではなく、情報（辞書）から認証を作成
    creds = service_account.Credentials.from_service_account_info(
        creds_info, scopes=SCOPES)
    return build('docs', 'v1', credentials=creds)

def extract_text_from_content(content):
    text_runs = []
    for element in content:
        if 'paragraph' in element:
            elements = element.get('paragraph').get('elements', [])
            for elem in elements:
                if 'textRun' in elem:
                    text_runs.append(elem.get('textRun').get('content'))
    return "".join(text_runs)


class ReadGoogleDocInput(BaseModel):
    document_id: str = Field(..., description="Google ドキュメントの ID")


class ReadGoogleDocTool(BaseTool):
    name: str = "read_google_doc"
    description: str = "指定した Google ドキュメントの全タブ（世界観、神話、登場人物、種族など）のテキスト内容を漏れなく全て読み込みます。"
    args_schema: Type[BaseModel] = ReadGoogleDocInput

    def _run(self, document_id: str) -> str:
        try:
            service = get_gdocs_service()
            doc = service.documents().get(documentId=document_id, includeTabsContent=True).execute()
            
            result = []
            if 'tabs' in doc:
                for tab in doc.get('tabs', []):
                    tab_props = tab.get('tabProperties', {})
                    title = tab_props.get('title', '無題のタブ')
                    tab_id = tab_props.get('tabId', '')
                    body = tab.get('documentTab', {}).get('body', {})
                    content = body.get('content', [])
                    text = extract_text_from_content(content)
                    result.append(f"=== タブ名: 【{title}】 (tabId: {tab_id}) ===\n{text}\n")
            else:
                body = doc.get('body', {})
                content = body.get('content', [])
                text = extract_text_from_content(content)
                result.append(f"=== ドキュメント本文 ===\n{text}")

            full_text = "\n".join(result)
            if not full_text.strip():
                return "ドキュメントは空です。"
            return full_text
        except Exception as e:
            return f"ドキュメントの読み込みに失敗しました: {str(e)}"


class AppendGoogleDocInput(BaseModel):
    document_id: str = Field(..., description="Google ドキュメントの ID")
    text: str = Field(..., description="追記するテキスト")
    target_tab_title: Optional[str] = Field(
        "co_writer_crewによる追加設定", 
        description="追記先のタブ名（デフォルト: 'co_writer_crewによる追加設定'）"
    )


class AppendGoogleDocTool(BaseTool):
    name: str = "append_to_google_doc"
    description: str = "指定した Google ドキュメントの特定のタブ（デフォルトは 'co_writer_crewによる追加設定'）の末尾にテキストを追記します。"
    args_schema: Type[BaseModel] = AppendGoogleDocInput

    def _run(self, document_id: str, text: str, target_tab_title: Optional[str] = "co_writer_crewによる追加設定") -> str:
        try:
            service = get_gdocs_service()
            doc = service.documents().get(documentId=document_id, includeTabsContent=True).execute()
            
            target_tab_id = None
            if 'tabs' in doc and target_tab_title:
                for tab in doc.get('tabs', []):
                    tab_props = tab.get('tabProperties', {})
                    if tab_props.get('title') == target_tab_title:
                        target_tab_id = tab_props.get('tabId')
                        break

            location = {}
            if target_tab_id:
                location['tabId'] = target_tab_id

            requests = [
                {
                    'insertText': {
                        'endOfSegmentLocation': location,
                        'text': f"\n\n{text}"
                    }
                }
            ]
            service.documents().batchUpdate(documentId=document_id, body={'requests': requests}).execute()
            target_str = f"タブ「{target_tab_title}」" if target_tab_id else "ドキュメント"
            return f"Google ドキュメントの{target_str}への書き込みが正常に完了しました。"
        except Exception as e:
            return f"ドキュメントへの書き込みに失敗しました: {str(e)}"