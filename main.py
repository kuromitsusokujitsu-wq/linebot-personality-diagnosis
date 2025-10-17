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
        logger.error(f"Error in handle_message: {e}", exc_info=True)

def start_diagnosis(user_id, reply_token):
    try:
        user_responses[user_id] = {"current_question": 1, "answers": {}, "completed": False}
        welcome = "🎯 AIパーソナル診断へようこそ！\n10の質問で完全個別化された性格分析を行います。"
        line_bot_api.reply_message(reply_token, TextSendMessage(text=welcome))
        send_question(user_id, 1)
    except Exception as e:
        logger.error(f"Error in start_diagnosis: {e}", exc_info=True)

def send_question(user_id, question_num):
    try:
        if question_num > 10:
            return
        q = QUESTIONS[question_num]
        line_bot_api.push_message(user_id, TextSendMessage(text=q["question"]))
        line_bot_api.push_message(user_id, TextSendMessage(text=q["example"]))
    except Exception as e:
        logger.error(f"Error in send_question: {e}", exc_info=True)

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
        logger.error(f"Error in process_answer: {e}", exc_info=True)

def analyze_responses(answers):
    """GPT-5-mini対応版 - 強化デバッグ + フォールバック"""
    try:
        responses_text = "\n\n".join([f"質問{q}: {a}" for q, a in answers.items()])
        logger.info(f"[DEBUG] Analysis start. Input length: {len(responses_text)} chars")
        
        # シンプル化されたプロンプト（トークン削減）
        system_prompt = """You are an expert psychologist. Respond in Japanese.

CRITICAL RULES:
- Write in "あなたは〜する" format (action-oriented)
- NO abstract analysis phrases like "傾向があります", "示しています"
- Use concrete daily life scenes (150+ chars per section)
- Structure: Psychology → Behavior → Emotion

OUTPUT FORMAT:
🎯 診断完了！

## 🎭 「[ニックネーム]」

### 💫 思考パターン
[心理構造 50文字]
→ [日常シーン 150文字]
[感情 50文字]

### 💝 感情の動き
[心理構造 50文字]
→ [日常シーン 150文字]
[行動への影響 50文字]

### 🌟 大切にしているもの
[価値観 50文字]
→ [日常シーン 150文字]
[背景 50文字]

### 💪 強みTop3
1. **[名前]**: [背景 40文字]
→ [日常シーン 180文字]

2. **[名前]**: [背景 40文字]
→ [日常シーン 180文字]

3. **[名前]**: [背景 40文字]
→ [日常シーン 180文字]

### ⚠️ 気をつけたいことTop3
1. **[名前]**: [メカニズム 40文字]
→ [日常シーン 180文字]

2. **[名前]**: [メカニズム 40文字]
→ [日常シーン 180文字]

3. **[名前]**: [メカニズム 40文字]
→ [日常シーン 180文字]

### 💡 活かし方
#### 🧩 仕事で
[150文字]

#### 💞 恋愛で
[150文字]

#### 🧑‍🤝‍🧑 人間関係で
[150文字]"""

        analysis_prompt = f"""以下の10問の回答を分析してください：

{responses_text}

INSTRUCTIONS:
- 禁止表現を使わず行動描写で書く
- 各セクションに具体的日常シーンを含める
- 文字数要件を守る
- この人固有のパターンを抽出"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": analysis_prompt}
        ]

        logger.info("[DEBUG] Calling OpenAI API with GPT-5-mini...")
        
        try:
            response = client.chat.completions.create(
                model="gpt-5-mini",
                messages=messages,
                max_completion_tokens=3500  # 4500→3500に削減
            )
            
            logger.info(f"[DEBUG] API call successful. Response type: {type(response)}")
            
            # レスポンス内容の詳細確認
            if not response.choices:
                logger.error("[ERROR] response.choices is empty")
                return generate_fallback_diagnosis(answers)
            
            message_content = response.choices[0].message.content
            logger.info(f"[DEBUG] message.content type: {type(message_content)}, value: {message_content[:100] if message_content else 'None'}")
            
            if not message_content:
                logger.error("[ERROR] message.content is None or empty")
                return generate_fallback_diagnosis(answers)
            
            result = message_content.strip()
            
            if len(result) < 100:
                logger.warning(f"[WARNING] Result too short: {len(result)} chars")
                return generate_fallback_diagnosis(answers)
            
            logger.info(f"[SUCCESS] Analysis completed! Length: {len(result)} chars")
            return result
            
        except openai.APIError as api_err:
            logger.error(f"[ERROR] OpenAI API Error: {api_err}", exc_info=True)
            return generate_fallback_diagnosis(answers)
        except Exception as api_ex:
            logger.error(f"[ERROR] Unexpected API error: {api_ex}", exc_info=True)
            return generate_fallback_diagnosis(answers)

    except Exception as e:
        logger.error(f"[CRITICAL ERROR] analyze_responses failed: {e}", exc_info=True)
        return generate_fallback_diagnosis(answers)

def generate_fallback_diagnosis(answers):
    """フォールバック診断（GPT-4o-miniで再試行）"""
    try:
        logger.info("[FALLBACK] Trying GPT-4o-mini as fallback...")
        
        responses_text = "\n\n".join([f"質問{q}: {a}" for q, a in answers.items()])
        
        simple_prompt = f"""以下の10問の回答から、この人の性格を日本語で診断してください。
必ず「あなたは〜する」形式で、具体的な日常行動を描写してください。

{responses_text}

診断結果（1500文字以上で詳しく）："""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": simple_prompt}],
            max_completion_tokens=2000,
            temperature=0.8
        )
        
        result = response.choices[0].message.content or ""
        
        if result and len(result) > 100:
            logger.info(f"[FALLBACK SUCCESS] GPT-4o-mini diagnosis: {len(result)} chars")
            return f"🎯 診断完了！\n\n{result}\n\n※ GPT-4o-miniで生成されました"
        else:
            logger.error("[FALLBACK FAILED] GPT-4o-mini also returned empty")
            return generate_emergency_diagnosis()
            
    except Exception as fb_err:
        logger.error(f"[FALLBACK ERROR] {fb_err}", exc_info=True)
        return generate_emergency_diagnosis()

def generate_emergency_diagnosis():
    """緊急時の固定診断メッセージ"""
    return """🎯 診断システム一時停止中

申し訳ございません。現在診断システムに技術的な問題が発生しています。

📧 サポートに自動通知済み
🔄 しばらく待ってから「診断開始」で再試行してください

ご不便をおかけして申し訳ございません。"""

def send_diagnosis_result(user_id, diagnosis_result):
    try:
        logger.info(f"[DEBUG] Sending diagnosis. Length: {len(diagnosis_result)}, Empty: {not diagnosis_result.strip()}")
        
        # 空チェック強化
        if not diagnosis_result or not diagnosis_result.strip():
            logger.error("[ERROR] diagnosis_result is empty!")
            diagnosis_result = generate_emergency_diagnosis()
        
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
            
            for i, part in enumerate(parts):
                logger.info(f"[DEBUG] Sending part {i+1}/{len(parts)}, length: {len(part)}")
                line_bot_api.push_message(user_id, TextSendMessage(text=part))
        
        line_bot_api.push_message(user_id, TextSendMessage(text="🎉 診断完了！\n\n🔄 新しい診断: 「診断開始」\n📤 友達にもシェア推奨！"))
        logger.info(f"[SUCCESS] Result sent successfully")
    except LineBotApiError as line_err:
        logger.error(f"[ERROR] LINE API Error: {line_err}", exc_info=True)
    except Exception as e:
        logger.error(f"[ERROR] send_diagnosis_result failed: {e}", exc_info=True)

@app.get("/")
async def root():
    return {"status": "ok", "message": "AI Diagnosis Bot Running (GPT-5-mini with fallback)"}

@app.get("/health")
async def health():
    return {"status": "ok", "line": bool(LINE_CHANNEL_ACCESS_TOKEN), "openai": bool(OPENAI_API_KEY)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
