from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai
import os
import uvicorn
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
client = openai.OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI()
user_responses = {}

# 質問定義（省略）
QUESTIONS = {
    1: {"question": "🤔 **質問1/10【認知構造】**\n\n最近、重要な決断をした体験について、その時の思考プロセスを具体的に教えてください。", "example": "💪 詳しく書くほど精密！"},
    2: {"question": "📚 **質問2/10【認知構造】**\n\n新しいことを学ぶとき、どんなアプローチを取りますか？", "example": "💪 詳しく書くほど精密！"},
    3: {"question": "😰 **質問3/10【感情構造】**\n\nストレスや困難な状況に直面したとき、どんな感情が湧き、どう対処していますか？", "example": "💪 詳しく書くほど精密！"},
    4: {"question": "✨ **質問4/10【感情構造】**\n\nあなたが最も充実感や喜びを感じる瞬間について教えてください。", "example": "💪 詳しく書くほど精密！"},
    5: {"question": "👥 **質問5/10【行動構造】**\n\n人間関係で困った経験について、その時の状況と行動を教えてください。", "example": "💪 詳しく書くほど精密！"},
    6: {"question": "🎯 **質問6/10【価値観構造】**\n\nあなたが「これだけは譲れない」と思うことは何ですか？", "example": "💪 詳しく書くほど精密！"},
    7: {"question": "🌟 **質問7/10【価値観構造】**\n\n人生で最も大切にしたい価値観を教えてください。", "example": "💪 詳しく書くほど精密！"},
    8: {"question": "🚀 **質問8/10【自己物語】**\n\n5年後、どんな自分になっていたいですか？", "example": "💪 詳しく書くほど精密！"},
    9: {"question": "⏰ **質問9/10【時間軸構造】**\n\n過去の自分と比べて、今いちばん変わったと思う点は？", "example": "💪 詳しく書くほど精密！"},
    10: {"question": "👨‍👩‍👧‍👦 **質問10/10【他者視点構造】**\n\n親しい友人があなたを紹介するとき、何と言うと思いますか？", "example": "💪 詳しく書くほど精密！"}
}

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get('X-Line-Signature', '')
    body = await request.body()
    try:
        handler.handle(body.decode('utf-8'), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return {"status": "ok"}

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        user_id = event.source.user_id
        user_message = event.message.text.strip()
        
        if user_id not in user_responses:
            user_responses[user_id] = {"current_question": 0, "answers": {}, "completed": False}
        
        user_data = user_responses[user_id]
        
        if user_message in ["診断", "start", "開始", "診断開始"] or user_data["current_question"] == 0:
            start_diagnosis(user_id, event.reply_token)
            return
        
        if user_data["completed"]:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="診断完了済み。新しい診断は「診断開始」"))
            return
        
        if user_data["current_question"] > 0:
            process_answer(user_id, user_message, event.reply_token)
    except Exception as e:
        logger.error(f"Error: {e}")

def start_diagnosis(user_id, reply_token):
    try:
        user_responses[user_id] = {"current_question": 1, "answers": {}, "completed": False}
        welcome = "🎯 AIパーソナル診断へようこそ！\n10の質問で完全個別化された性格分析を行います。"
        line_bot_api.reply_message(reply_token, TextSendMessage(text=welcome))
        send_question(user_id, 1)
    except Exception as e:
        logger.error(f"Error: {e}")

def send_question(user_id, question_num):
    try:
        if question_num > 10:
            return
        q = QUESTIONS[question_num]
        line_bot_api.push_message(user_id, TextSendMessage(text=q["question"]))
        line_bot_api.push_message(user_id, TextSendMessage(text=q["example"]))
    except Exception as e:
        logger.error(f"Error: {e}")

def process_answer(user_id, answer, reply_token):
    try:
        user_data = user_responses[user_id]
        current_q = user_data["current_question"]
        user_data["answers"][current_q] = answer
        
        if current_q < 10:
            user_data["current_question"] = current_q + 1
            line_bot_api.reply_message(reply_token, TextSendMessage(text=f"✅ 回答ありがとう！続いて質問{current_q + 1}です。"))
            send_question(user_id, current_q + 1)
        else:
            user_data["completed"] = True
            line_bot_api.reply_message(reply_token, TextSendMessage(text="🎉 全質問完了！分析中..."))
            diagnosis = analyze_responses(user_data["answers"])
            send_diagnosis_result(user_id, diagnosis)
    except Exception as e:
        logger.error(f"Error: {e}")

def analyze_responses(answers):
    """GPT-5-mini対応版 - temperatureパラメータなし"""
    try:
        responses_text = "\n\n".join([f"質問{q}: {a}" for q, a in answers.items()])
        logger.info(f"Analysis start with GPT-5-mini. Length: {len(responses_text)}")
        
        system_prompt = """あなたは世界最高峰の心理分析専門家です。日本語で回答してください。

【CRITICAL RULES - 絶対厳守】

❌ **絶対禁止表現リスト**：
・「〜という表現からわかるように」
・「〜を示しています」
・「〜な傾向があります」
・「〜と言えるでしょう」
・「〜と考えられます」
・「分析すると」
・「〜が見て取れます」
・観察者視点の解説文

✅ **必須要件**：
・すべて「あなたは〜な場面でこう動く」形式で記述
・日常の具体的な行動シーンで描写
・読者が「あ、これ自分だ」と思える瞬間描写
・心理構造 → 行動例 → 感情の裏づけ の3層構造

【記述の黄金パターン】
各セクションは必ずこの構造：
1. 心理構造（50-80文字）
2. → 具体的な日常行動シーン（150-250文字）
3. 感情・動機の裏づけ（50-80文字）

【ダメな例】
❌ 「あなたは迅速な意思決定を重視する傾向があります」
❌ 「この表現から行動力の高さが示されています」

【良い例】
✅ 「何か問題が起きたとき、あなたはまず深呼吸して全体像を掴もうとする。頭の中で図を描いたり、ノートに書き出したりして『ここが本質だな』と確信した瞬間に動き出す。周りが『もう少し慎重に...』と言っても、あなたの中で確信があれば止まらない。」

【セルフチェック項目】
出力前に以下を自己確認：
□ すべての見出しを含んでいるか
□ 各セクションに「心理→行動→感情」が入っているか
□ 禁止表現が一切含まれていないか
□ 各行動シーンが150文字以上あるか
□ 読者が自分の日常を思い浮かべられる具体性があるか

【出力フォーマット】
🎯 診断完了！

## 🎭 「[日常行動が見える二つ名]」

### 💫 あなたの思考パターン
[心理構造 50-80文字]
→ [日常の思考シーン 150-250文字：具体的な場面・行動・心の動きを詳細に]
[感情的裏づけ 50-80文字]

### 💝 感情の動き
[心理構造 50-80文字]
→ [日常の感情シーン 150-250文字：どんな場面でどう感じ、どう行動するか]
[行動への影響 50-80文字]

### 🌟 大切にしているもの
[価値観の核 50-80文字]
→ [価値観が現れる日常シーン 150-250文字：この価値観がどう行動に出るか]
[この価値観が生まれた背景 50-80文字]

### 📖 あなたの変化
[過去との違い 50-80文字]
→ [変化が見える具体的シーン 150-250文字：以前と今でどう行動が変わったか]
[今後の方向性 50-80文字]

### 🎯 周りから見たあなた
[他者評価 50-80文字]
→ [友人があなたを語るシーン 120-200文字：友人の視点での具体的描写]
[自己認識とのギャップ 50-80文字]

### 💪 強みTop3（行動描写付き）
1. **[強みの名前]**: [心理的背景 40-60文字]
　→ [この強みが発揮される具体的な日常シーン 180-280文字：どんな状況で、どう動き、どんな結果を生むか]

2. **[強みの名前]**: [心理的背景 40-60文字]
　→ [具体的な日常シーン 180-280文字]

3. **[強みの名前]**: [心理的背景 40-60文字]
　→ [具体的な日常シーン 180-280文字]

### ⚠️ 気をつけたいことTop3（行動描写付き）
1. **[課題の名前]**: [心理的メカニズム 40-60文字]
　→ [この課題が現れる具体的な日常シーン 180-280文字：どんな場面で、どう困り、どう感じるか]

2. **[課題の名前]**: [心理的メカニズム 40-60文字]
　→ [具体的な日常シーン 180-280文字]

3. **[課題の名前]**: [心理的メカニズム 40-60文字]
　→ [具体的な日常シーン 180-280文字]

### 💡 活かし方

#### 🧩 仕事で
[あなたが仕事中にとる具体的な行動シーン 150-250文字：朝の仕事開始から、会議、作業中の様子など]

#### 💞 恋愛で
[あなたが恋愛中にとる具体的な行動シーン 150-250文字：デート、コミュニケーション、喧嘩の時など]

#### 🧑‍🤝‍🧑 人間関係で
[あなたが対人関係でとる具体的な行動シーン 150-250文字：友人との会話、初対面、困った時など]

### 📋 今週の行動処方箋
1. **[超具体的行動タイトル]**
　→ [なぜ効果的か + 実践シーン 120-200文字：いつ、どこで、どうやるか]

2. **[超具体的行動タイトル]**
　→ [なぜ効果的か + 実践シーン 120-200文字]

3. **[超具体的行動タイトル]**
　→ [なぜ効果的か + 実践シーン 120-200文字]

この分析が、あなたの日常に新しい気づきをもたらすことを願っています。"""

        analysis_prompt = f"""以下の10問の回答を分析してください：

{responses_text}

【最重要指示】
1. 禁止表現を一切使わず、すべて行動描写で書いてください
2. 各セクションで「心理構造→行動例→感情の裏づけ」を必ず含めてください
3. 読者が自分の日常の姿を思い浮かべられる具体的なシーンを描いてください
4. 文字数要件を厳守してください（行動シーン150文字以上）
5. この人の回答の言葉選び・エピソードから、この人だけの固有パターンを抽出してください

出力前にセルフチェックを行い、完璧な診断結果を作成してください。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": analysis_prompt}
        ]

        logger.info("Calling OpenAI API with GPT-5-mini (default temperature=1)...")
        response = client.chat.completions.create(
            model="gpt-5-mini",  # ✅ GPT-5-mini に変更
            messages=messages,
            max_completion_tokens=4500
            # ⚠️ temperature, top_p, presence_penalty, frequency_penalty は削除
            # GPT-5-mini はデフォルト値 (temperature=1) のみサポート
        )
        
        result = response.choices[0].message.content or ""
        
        # 簡易的な禁止語チェック（ログ記録のみ）
        banned_patterns = ["傾向があります", "示しています", "と言えるでしょう", "と考えられます", "分析すると", "が見て取れます"]
        found_banned = [b for b in banned_patterns if b in result]
        if found_banned:
            logger.warning(f"⚠️ 禁止語検出: {found_banned}")
        
        logger.info(f"✅ Analysis completed with GPT-5-mini! Length: {len(result)} chars")
        return result

    except Exception as e:
        logger.error(f"❌ ERROR: {type(e).__name__}: {str(e)}")
        return "分析中にエラーが発生しました。もう一度お試しください。"

def send_diagnosis_result(user_id, diagnosis_result):
    try:
        max_length = 5000
        if len(diagnosis_result) <= max_length:
            line_bot_api.push_message(user_id, TextSendMessage(text=diagnosis_result))
        else:
            parts = []
            current = ""
            for line in diagnosis_result.split('\n'):
                if len(current + line + '\n') <= max_length:
                    current += line + '\n'
                else:
                    if current:
                        parts.append(current)
                    current = line + '\n'
            if current:
                parts.append(current)
            
            for part in parts:
                line_bot_api.push_message(user_id, TextSendMessage(text=part))
        
        line_bot_api.push_message(user_id, TextSendMessage(text="🎉 診断完了！\n\n🔄 新しい診断: 「診断開始」\n📤 友達にもシェア推奨！"))
        logger.info(f"Result sent successfully")
    except Exception as e:
        logger.error(f"Error: {e}")

@app.get("/")
async def root():
    return {"status": "ok", "message": "AI Diagnosis Bot Running (GPT-5-mini)"}

@app.get("/health")
async def health():
    return {"status": "ok", "line": bool(LINE_CHANNEL_ACCESS_TOKEN), "openai": bool(OPENAI_API_KEY)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
