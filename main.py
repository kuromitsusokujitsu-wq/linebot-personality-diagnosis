from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
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

# インメモリセッション管理
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
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは心理学とパーソナリティ分析の専門家です。深い洞察力で人の内面を見抜き、温かく支援的なアドバイスを提供します。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.8
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI API Error: {e}")
        return "🔍 興味深い回答ですね。あなたらしさが表れていると感じます。"

def mini_feedback(answers: List[str], just_answered_index: int) -> str:
    """ミニ所見を生成"""
    prompt = f"""心理学専門家として、この回答から見える深層心理を分析してください。

【分析指針】
- 表面的な要約ではなく、心理的パターンを読み取る
- 行動の背景にある価値観や動機を推察する
- 温かく洞察力のある所見にする（150字以内）

【質問】{QUESTIONS[just_answered_index]['text']}
【回答】{answers[just_answered_index]}

この回答から見える心理的特徴を1つの所見として述べてください。"""
    
    return call_openai_api(prompt, 200)

def final_diagnosis(answers: List[str]) -> str:
    """最終診断を生成"""
    
    # 回答を整理
    answers_text = ""
    for i in range(len(answers)):
        answers_text += f"Q{i+1}: {QUESTIONS[i]['text']}\n回答: {answers[i]}\n\n"
    
    # 強化されたプロンプト
    prompt = f"""あなたは臨床心理学者です。以下の12の質問への回答を深層心理学的に分析し、その人の本質的な性格構造を解明してください。

【重要】以下のフォーマットを厳密に守って出力してください：

{answers_text}

【分析要求】
1. 回答の要約ではなく、深層心理の分析を行う
2. 行動パターンから内面の動機構造を読み取る
3. 潜在的な強みと課題を心理学的に解釈する
4. 実用的で具体的なアドバイスを提供する

【必須出力フォーマット】
## 🎭 「[12-20文字の診断タイプ名]」

### 💫 あなたの思考構造
[認知パターンと情報処理の特徴を2-3文で]

### 💝 感情のクセ
[感情の動きや感情調節の傾向を2-3文で]

### 🌟 価値観の核
[最も大切にしている根本的価値観を2-3文で]

### 📖 物語の型
[人生への取り組み方や成長パターンを2-3文で]

### 💪 強みTop3
1. [具体的な強み1]
2. [具体的な強み2]
3. [具体的な強み3]

### ⚠️ 注意点Top3
1. [具体的な注意点1]
2. [具体的な注意点2]
3. [具体的な注意点3]

### 💡 活かし方ガイド

#### 🧩 仕事での活かし方
[2-3文の具体的アドバイス]

#### 💞 恋愛での活かし方
[2-3文の具体的アドバイス]

#### 🧑‍🤝‍🧑 対人関係での活かし方
[2-3文の具体的アドバイス]

### 📋 今週の処方箋
1. [具体的行動1]
2. [具体的行動2]
3. [具体的行動3]

このフォーマットを必ず守り、心理学的洞察に基づいた深い分析を行ってください。"""
    
    result = call_openai_api(prompt, 2500)
    
    # フォールバック診断の改善
    if "🔍 興味深い回答ですね" in result:
        return get_enhanced_fallback_diagnosis()
    
    return result

def get_enhanced_fallback_diagnosis():
    """改善されたフォールバック診断"""
    return """## 🎭 「内省する成長探求者タイプ」

### 💫 あなたの思考構造
物事を多角的に捉え、表面的な答えに満足せず本質を探ろうとする深い思考パターンをお持ちです。経験から学び取る能力が高く、常に成長への道筋を見出そうとする意識的な思考プロセスが特徴的です。

### 💝 感情のクセ
感情を大切にしながらも冷静に観察し、感情に流されすぎないよう調整する術を身につけています。内面の微細な変化にも敏感で、自分の心の動きを客観視する高いメタ認知能力をお持ちです。

### 🌟 価値観の核
真の成長と自己実現を最重要視し、他者との調和を保ちながらも自分らしさを失わない生き方を追求しています。誠実さと向上心が価値観の根幹にあり、人生を意味のあるものにしたいという強い欲求があります。

### 📖 物語の型
継続的な自己改善を軸とした成長ストーリーを描いています。挫折や困難も学習機会として捉え、螺旋状に成長していく力強さがあります。自分なりのペースで着実に前進する姿勢が一貫しています。

### 💪 強みTop3
1. 深い自己理解力と内省的思考能力
2. 経験を学びに変換する高い学習意欲
3. 他者への共感性と建設的なバランス感覚

### ⚠️ 注意点Top3
1. 完璧主義的傾向で自分を追い込みやすい
2. 考えすぎて行動のタイミングを逃しがち
3. 他者の期待に敏感で自分の軸がブレることがある

### 💡 活かし方ガイド

#### 🧩 仕事での活かし方
あなたの深い分析力と継続的改善マインドは、長期的プロジェクトや戦略立案で威力を発揮します。急がず質を重視できる環境で、持ち前の洞察力を活かしてください。

#### 💞 恋愛での活かし方
相手を理解しようとする真摯な姿勢と成長志向は、深い信頼関係の基盤となります。お互いを高め合える関係性を築き、ゆっくりと絆を深めていくアプローチが最適です。

#### 🧑‍🤝‍🧑 対人関係での活かし方
優れた傾聴力と共感性を活かし、人の相談に乗る役割で信頼を築けます。自分らしさを大切にしながら、自然体で人と関わることで真の魅力が伝わります。

### 📋 今週の処方箋
1. 1日20分の振り返りタイムを設けて思考と行動のバランスを取る
2. 小さな達成を積み重ね、完璧主義の罠を回避する
3. 自分の感情を受け入れる「セルフ・コンパッション」の時間を持つ"""

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
        if text in ["診断開始", "開始", "はじめ", "スタート", "診断", "start"]:
            reply_text = "🔍 次世代性格診断AI へようこそ！\n\n12問の質問で、あなたの思考構造・感情パターン・価値観を多角的に分析します。\n各回答後にミニ所見をお返しし、最後に詳細なパーソナリティレポートを作成します。\n\n個人を特定する情報は不要です。\n準備ができましたら「はい」と送ってください。"
        elif text in ["はい", "ok", "同意", "始める", "yes"]:
            SessionManager.create_session(user_id)
            q1 = QUESTIONS[0]
            reply_text = f"Q{q1['id']}: {q1['text']}\n\n{q1['example']}\n\n（できるだけ具体的にお答えください）"
        else:
            reply_text = "「診断開始」と送ると始まります。"
    else:
        idx = session["index"]
        answers = session["answers"]
        answers.append(text)
        
        SessionManager.update_session(user_id, idx + 1, answers)
        
        mini = mini_feedback(answers, idx)
        
        if len(answers) < len(QUESTIONS):
            next_q = QUESTIONS[len(answers)]
            reply_text = f"{mini}\n\n━━━━━━━━━━\n\nQ{next_q['id']}: {next_q['text']}\n\n{next_q['example']}"
        else:
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
