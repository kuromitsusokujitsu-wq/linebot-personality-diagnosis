from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai
import os
import json
import logging
from typing import Dict, List, Optional

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# 環境変数から設定を読み込み
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# LINE Bot APIの初期化
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# OpenAI APIの初期化
openai.api_key = OPENAI_API_KEY

# 質問データ
QUESTIONS = [
    {
        "id": 1,
        "text": "最近、「自分らしい」と思えた出来事を教えてください。",
        "example": "例：自分のアイデアが採用されたとき、友達を笑わせられたとき、自然の中で心が落ち着いたとき…など。"
    },
    {
        "id": 2,
        "text": "思ったようにいかなかった体験と、そこから気づいたことはありますか？",
        "example": "例：仕事でミスをした、人間関係で気まずくなった、挑戦したけど結果が出なかった…など。「そのとき、なぜそうなったと思うか？」まで教えてください。"
    },
    {
        "id": 3,
        "text": "周囲の人から「すごいね」「助かった」と言われることはどんなことですか？",
        "example": "例：聞き上手と言われる、整理が得意、いつも前向き、細かいことに気づく…など。"
    },
    {
        "id": 4,
        "text": "グループで動くとき、自然とどんな役割をしていることが多いですか？",
        "example": "例：まとめ役、聞き役、盛り上げ役、裏方で支えるタイプ、静かに観察して意見を出す…など。"
    },
    {
        "id": 5,
        "text": "最近、感情が大きく動いた出来事を一つ教えてください。",
        "example": "例：嬉しくて泣いた、腹が立った、感動した、不安だった、安心した…など。そのとき、どうやって気持ちを落ち着けましたか？"
    },
    {
        "id": 6,
        "text": "物事を決めるとき、どちらの傾向が強いですか？",
        "example": "例：「直感でピンときたら動く」「理由を整理してから動く」どちらも当てはまる場合は、その割合を感覚で教えてください（例：直感6割・理屈4割）。"
    },
    {
        "id": 7,
        "text": "心身が疲れたとき、どうやって回復していますか？",
        "example": "例：寝る・自然の中に行く・お風呂に浸かる・好きな人に会う・一人になる・音楽を聴く…など。"
    },
    {
        "id": 8,
        "text": "あなたが大切にしている価値は何ですか？",
        "example": "例：自由・信頼・挑戦・愛・誠実・安定・成長・感謝…など、直感で選んでください。"
    },
    {
        "id": 9,
        "text": "子どもの頃から変わっていない「好きなこと・苦手なこと」は？",
        "example": "例：好き→絵を描く、探検、考えること／苦手→争うこと、大人数、計算など。"
    },
    {
        "id": 10,
        "text": "最近の学びや発見で、「世界の見え方」が変わったことはありますか？",
        "example": "例：本や動画で感動したこと、人の言葉でハッとしたこと、体験を通じて気づいたこと…など。"
    },
    {
        "id": 11,
        "text": "これからの「理想の1日」を、少しだけ想像して教えてください。",
        "example": "例：朝はカフェでゆっくり仕事、午後は海辺を散歩、夜は家族や仲間と語らう…など。"
    },
    {
        "id": 12,
        "text": "1年後のあなたが、今のあなたに手紙を書くとしたら何と言いますか？",
        "example": "例：「焦らなくて大丈夫」「あの挑戦、続けて正解だった」「もう少し休んでいいよ」など。"
    }
]

# システムプロンプト
SYSTEM_PROMPT = """あなたは「次世代性格診断AI」。目的は、自由回答から
①認知構造 ②感情構造 ③行動傾向 ④価値観構造 ⑤自己物語
の5層を連続スコア化（0-100）し、かつ人間が読める日本語レポートに翻訳すること。

【スコア定義（0-100）】
- cognition_abstractness：抽象志向（概念/メタ思考の度合い）
- cognition_systemizing：体系化・因果で語る傾向
- affect_valence：ポジ/ネガの平均傾向
- affect_volatility：感情振幅（ゆらぎ）
- behavior_decisiveness：決断の速さ（躊躇の少なさ）
- behavior_persistence：粘り強さ/継続力
- values_autonomy：自律・自由志向
- values_benevolence：共感・利他志向
- narrative_coherence：過去-現在-未来の一貫性
- narrative_agency：自己効力感（自分が物語を動かす感覚）

診断ネーム（タイプ名）は12〜20文字以内。名詞＋象徴語で構成。
表現トーンは「温かく、内省的、少し詩的」で統一する。"""

# インメモリセッション管理（本格運用時はRedisやDBに移行）
sessions: Dict[str, Dict] = {}

class SessionManager:
    @staticmethod
    def get_session(user_id: str) -> Optional[Dict]:
        return sessions.get(user_id)
    
    @staticmethod
    def create_session(user_id: str):
        sessions[user_id] = {
            "index": 0,
            "answers": []
        }
    
    @staticmethod
    def update_session(user_id: str, index: int, answers: List[str]):
        if user_id in sessions:
            sessions[user_id]["index"] = index
            sessions[user_id]["answers"] = answers
    
    @staticmethod
    def clear_session(user_id: str):
        if user_id in sessions:
            del sessions[user_id]

def call_openai_api(prompt: str, max_tokens: int = 200) -> str:
    """OpenAI APIを呼び出す"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI API Error: {e}")
        return "分析中です..."

def mini_feedback(answers: List[str], just_answered_index: int) -> str:
    """ミニ所見を生成"""
    prompt = f"""あなたは性格診断AI。ユーザーの最新回答(Q{just_answered_index+1})を見て、
「観察事実2点」→「仮説的ミニ所見2〜3文」→「日常描写1文」で返してください。

- 断定は避け、「〜が見え始めました」「示唆されます」を使う
- 日常描写は"あなた"主語で、感情・行動・場面を1セットで
- 150字以内の短い返答

Q{just_answered_index+1}: {QUESTIONS[just_answered_index]['text']}
回答: {answers[just_answered_index]}"""
    
    return call_openai_api(prompt, 200)

def final_diagnosis(answers: List[str]) -> str:
    """最終診断を生成"""
    answers_text = "\n\n".join([
        f"Q{i+1}: {QUESTIONS[i]['text']}\n回答: {answers[i]}"
        for i in range(len(answers))
    ])
    
    prompt = f"""{SYSTEM_PROMPT}

以下の12回答を分析し、指定フォーマットで出力してください：

{answers_text}"""
    
    return call_openai_api(prompt, 2000)

@app.get("/")
async def root():
    return {"message": "LINEbot Personality Diagnosis is running!"}

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers['X-Line-Signature']
    body = await request.body()
    
    try:
        handler.handle(body.decode(), signature)
    except InvalidSignatureError:
        logger.error("Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    
    session = SessionManager.get_session(user_id)
    
    if not session:
        # 初期案内
        if text in ["診断開始", "開始", "はじめ", "スタート", "診断", "start"]:
            reply_text = """🔍 次世代性格診断AI へようこそ！

12問の質問で、あなたの思考構造・感情パターン・価値観を多角的に分析します。
各回答後にミニ所見をお返しし、最後に詳細なパーソナリティレポートを作成します。

個人を特定する情報は不要です。
準備ができましたら「はい」と送ってください。"""
        elif text in ["はい", "ok", "同意", "始める", "yes"]:
            SessionManager.create_session(user_id)
            q1 = QUESTIONS[0]
            reply_text = f"Q{q1['id']}: {q1['text']}\n\n{q1['example']}\n\n（できるだけ具体的にお答えください）"
        else:
            reply_text = "「診断開始」と送ると始まります。"
    else:
        # 回答処理
        idx = session["index"]
        answers = session["answers"]
        answers.append(text)
        
        SessionManager.update_session(user_id, idx + 1, answers)
        
        # ミニ所見生成
        mini = mini_feedback(answers, idx)
        
        if len(answers) < len(QUESTIONS):
            # 次の質問
            next_q = QUESTIONS[len(answers)]
            reply_text = f"{mini}\n\n━━━━━━━━━━\n\nQ{next_q['id']}: {next_q['text']}\n\n{next_q['example']}"
        else:
            # 最終診断
            diagnosis = final_diagnosis(answers)
            reply_text = f"🎯 診断完了！\n\n【あなたの性格診断結果】\n\n{diagnosis}"
            SessionManager.clear_session(user_id)
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
