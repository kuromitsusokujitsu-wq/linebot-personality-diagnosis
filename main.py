from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai
import os
import uvicorn
import logging

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 環境変数
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

logger.info(f"ENV CHECK - LINE Token: {bool(LINE_CHANNEL_ACCESS_TOKEN)}, Secret: {bool(LINE_CHANNEL_SECRET)}, OpenAI: {bool(OPENAI_API_KEY)}")

# 初期化
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
client = openai.OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI()
user_responses = {}

# 質問定義
QUESTIONS = {
    1: {
        "question": "🤔 **質問1/10【認知構造】**\n\n最近、重要な決断をした体験について、その時の思考プロセスを具体的に教えてください。何を考え、何を重視し、最終的にどう判断したかを詳しく。",
        "example": "📝 **記入例**\n先月、転職するかどうかで悩んでいました。まず現在の仕事の不満点をリストアップし、転職先の条件と比較しました。でも最終的な決め手は「直感的にワクワクするか」でした。\n\n💡 **ポイント**: 具体的な状況・思考プロセス・判断基準を詳しく！"
    },
    2: {
        "question": "📚 **質問2/10【認知構造】**\n\n新しいことを学ぶとき、どんなアプローチを取りますか？学習方法、動機、継続の仕方について、あなたなりのやり方を教えてください。",
        "example": "📝 **記入例**\n興味を持った分野は、まずYouTubeで概要を掴んでから本を読みます。一人で黙々とやるより、同じ興味を持つ人とディスカッションする方が理解が深まります。\n\n💡 **ポイント**: 学習スタイル・モチベーション・継続のコツを具体的に！"
    },
    3: {
        "question": "😰 **質問3/10【感情構造】**\n\nストレスや困難な状況に直面したとき、どんな感情が湧き、どう対処していますか？最近の具体的な経験も含めて教えてください。",
        "example": "📝 **記入例**\n仕事でトラブルが起きると、まず「なんで私が...」という怒りが湧きます。でもその後すぐに「どうしよう」という不安に変わります。対処法としては、一旦深呼吸して問題を紙に書き出します。\n\n💡 **ポイント**: 感情の変化・対処方法・具体的なエピソードを詳しく！"
    },
    4: {
        "question": "✨ **質問4/10【感情構造】**\n\nあなたが最も充実感や喜びを感じる瞬間について教えてください。それはなぜそう感じるのか、理由も含めて。",
        "example": "📝 **記入例**\n後輩に仕事を教えて、その人が「わかりました！」と目を輝かせる瞬間が最高に嬉しいです。自分の知識や経験が誰かの役に立っている実感があります。\n\n💡 **ポイント**: 具体的なシーン・なぜ嬉しいのか・価値観との関係を詳しく！"
    },
    5: {
        "question": "👥 **質問5/10【行動構造】**\n\n人間関係で困った経験について、その時の状況と、あなたがとった行動、そしてその行動を選んだ理由を教えてください。",
        "example": "📝 **記入例**\n同僚との意見対立で職場の雰囲気が悪くなった時、私は直接話し合いを提案しました。対立を避けるより、建設的に解決したい性格だと思います。\n\n💡 **ポイント**: 具体的な状況・とった行動・選択理由を詳しく！"
    },
    6: {
        "question": "🎯 **質問6/10【価値観構造】**\n\nあなたが「これだけは譲れない」と思うことは何ですか？それはなぜ大切で、どんな経験からそう思うようになったかも教えてください。",
        "example": "📝 **記入例**\n「人を裏切らない」ことは絶対に譲れません。学生時代に親友だと思っていた人に陰で悪口を言われていたことがあり、信頼関係の大切さを痛感しました。\n\n💡 **ポイント**: 譲れないこと・大切な理由・形成された経験を詳しく！"
    },
    7: {
        "question": "🌟 **質問7/10【価値観構造】**\n\n人生で最も大切にしたい価値観や生き方について教えてください。理想的な人生とはどんなものか、あなたの考えを聞かせてください。",
        "example": "📝 **記入例**\n「自分らしく、でも人の役に立つ」生き方を大切にしたいです。派手な成功より、身近な人から「ありがとう」と言われる機会の多い人生の方が価値があると思います。\n\n💡 **ポイント**: 大切な価値観・理想の人生像を詳しく！"
    },
    8: {
        "question": "🚀 **質問8/10【自己物語】**\n\n5年後、どんな自分になっていたいですか？その理想の自分になるために、今何を大切にしていますか？",
        "example": "📝 **記入例**\n5年後は、専門分野で一定の地位を築きつつ、後輩の育成にも力を入れている自分でいたいです。今は技術スキルの向上はもちろん、人とのコミュニケーション能力も意識的に鍛えています。\n\n💡 **ポイント**: 具体的な理想像・そのための現在の取り組みを詳しく！"
    },
    9: {
        "question": "⏰ **質問9/10【時間軸構造】**\n\n過去の自分と比べて、今いちばん変わったと思う点は？その変化をどう捉えていますか？",
        "example": "📝 **記入例**\n学生時代は人の目ばかり気にしていましたが、今は自分の価値観を大切にするようになりました。この変化は良いことだと思っていて、もっと自分軸を大切にしていきたいです。\n\n💡 **ポイント**: 具体的な変化・変化への評価・きっかけを詳しく！"
    },
    10: {
        "question": "👨‍👩‍👧‍👦 **質問10/10【他者視点構造】**\n\n親しい友人があなたを他の人に紹介するとき、何と言うと思いますか？また、それは自分が思う自分の特徴と同じですか？",
        "example": "📝 **記入例**\n友人は「彼女は一見おとなしそうだけど、実はすごく芯が強くて、困った時に頼りになる人」と言うと思います。私自身は「優柔不断で心配性」だと思っているので、友人の方が私を強く見てくれているのかもしれません。\n\n💡 **ポイント**: 友人の紹介予想・自己認識との違いを詳しく！"
    }
}

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get('X-Line-Signature', '')
    body = await request.body()
    logger.info(f"Callback received")
    
    try:
        handler.handle(body.decode('utf-8'), signature)
    except InvalidSignatureError:
        logger.error("Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    return {"status": "ok"}

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        user_id = event.source.user_id
        user_message = event.message.text.strip()
        logger.info(f"Message from {user_id}: {user_message}")
        
        if user_id not in user_responses:
            user_responses[user_id] = {"current_question": 0, "answers": {}, "completed": False}
        
        user_data = user_responses[user_id]
        
        if user_message in ["診断", "start", "開始", "診断開始"] or user_data["current_question"] == 0:
            start_diagnosis(user_id, event.reply_token)
            return
        
        if user_data["completed"]:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="診断完了済み。新しい診断は「診断開始」と送信してください。"))
            return
        
        if user_data["current_question"] > 0:
            process_answer(user_id, user_message, event.reply_token)
            
    except Exception as e:
        logger.error(f"Error in handle_message: {e}", exc_info=True)

def start_diagnosis(user_id, reply_token):
    try:
        user_responses[user_id] = {"current_question": 1, "answers": {}, "completed": False}
        welcome = """🎯 **AIパーソナル診断へようこそ！**

このシステムでは10の質問で、あなただけの完全個別化された性格分析を行います。

✨ **特徴**
• 既存診断を超える精密分析
• あなただけの固有パターンを発見
• 実生活で活用できる具体的アドバイス

📝 **回答のコツ**
• 詳しく書くほど精密な分析が可能
• 具体的なエピソードを含めて
• 思ったことを自由に表現してください

それでは質問1から始めましょう！"""
        
        line_bot_api.reply_message(reply_token, TextSendMessage(text=welcome))
        send_question(user_id, 1)
        logger.info(f"Diagnosis started for {user_id}")
    except Exception as e:
        logger.error(f"Error in start_diagnosis: {e}")

def send_question(user_id, question_num):
    try:
        if question_num > 10:
            return
        q = QUESTIONS[question_num]
        line_bot_api.push_message(user_id, TextSendMessage(text=q["question"]))
        line_bot_api.push_message(user_id, TextSendMessage(text=q["example"]))
        line_bot_api.push_message(user_id, TextSendMessage(text="💪 詳しく教えていただくほど、より精密で個人的な診断が可能になります！"))
        logger.info(f"Question {question_num} sent to {user_id}")
    except Exception as e:
        logger.error(f"Error in send_question: {e}")

def process_answer(user_id, answer, reply_token):
    try:
        user_data = user_responses[user_id]
        current_q = user_data["current_question"]
        user_data["answers"][current_q] = answer
        logger.info(f"Answer {current_q} saved for {user_id}")
        
        if current_q < 10:
            user_data["current_question"] = current_q + 1
            line_bot_api.reply_message(reply_token, TextSendMessage(text=f"✅ 質問{current_q}の回答ありがとうございます！\n\n続いて質問{current_q + 1}です。"))
            send_question(user_id, current_q + 1)
        else:
            user_data["completed"] = True
            line_bot_api.reply_message(reply_token, TextSendMessage(text="🎉 全ての質問にお答えいただき、ありがとうございました！\n\n分析中です...少しお待ちください。"))
            logger.info(f"Starting analysis for {user_id}")
            diagnosis = analyze_responses(user_data["answers"])
            send_diagnosis_result(user_id, diagnosis)
    except Exception as e:
        logger.error(f"Error in process_answer: {e}")

def analyze_responses(answers):
    """革命的AI診断分析 - 完全版"""
    try:
        responses_text = "\n\n".join([f"質問{q}: {a}" for q, a in answers.items()])
        logger.info(f"Starting GPT analysis. Response length: {len(responses_text)} chars")
        
        system_prompt = """あなたは世界最高峰の心理分析専門家「Dr. Insight Genesis」です。

【CRITICAL MISSION】
この人の10の回答から、完全個別化された深層心理分析を実行せよ。
一般論は絶対に禁止。この人だけに当てはまる固有の特徴を特定せよ。

【分析フレームワーク】
1. **認知スタイル**: 意思決定・学習・問題解決の独自パターン
2. **感情処理**: ストレス反応・喜びの源泉・感情表現の特徴
3. **行動特性**: 対人関係・行動選択の基準
4. **価値観の核**: 譲れないもの・人生哲学・理想像
5. **成長軌跡**: 過去からの変化・未来ビジョン
6. **自己認知**: 他者視点とのギャップ分析

【必須要件】
- 回答の具体的なエピソードや表現を必ず引用して分析
- この人の言葉選び・表現スタイルから個性を読み取る
- 一般的な表現は使わず、この人固有の特徴を具体的に描写
- 各セクション最低150文字以上で詳細に分析
- 「なんで私のことそんなに知ってるの？」と驚くレベルの的中感

【出力フォーマット】
🎯 診断完了！

【あなたの診断結果】

## 🎭 「[この人を表す独自の二つ名]」

### 💫 あなたの思考構造
[具体的なエピソードを引用しながら、この人の思考パターンを詳細分析。意思決定・学習方法の独自性を150文字以上で]

### 💝 感情のクセ
[ストレス対処や喜びの瞬間から、感情処理の独自性を詳細分析。この人だけの感情の動き方を150文字以上で]

### 🌟 価値観の核
[譲れないもの・人生哲学から、価値観の深層構造を詳細分析。この人の判断基準を150文字以上で]

### 📖 物語の型
[過去との比較・未来ビジョンから、成長ストーリーを詳細分析。変化の方向性を150文字以上で]

### 🎯 他者から見たあなた
[友人の評価と自己認識のギャップを詳細分析。客観的な魅力を100文字以上で]

### 💪 強みTop3
1. **[具体的な強み]**: [実生活での活かし方を具体的に]
2. **[具体的な強み]**: [実生活での活かし方を具体的に]
3. **[具体的な強み]**: [実生活での活かし方を具体的に]

### ⚠️ 注意点Top3
1. **[具体的な課題]**: [改善アプローチを具体的に]
2. **[具体的な課題]**: [改善アプローチを具体的に]
3. **[具体的な課題]**: [改善アプローチを具体的に]

### 💡 活かし方ガイド

#### 🧩 仕事での活かし方
[この人の特性を踏まえた具体的アドバイス100文字以上]

#### 💞 恋愛での活かし方
[この人の特性を踏まえた具体的アドバイス100文字以上]

#### 🧑‍🤝‍🧑 対人関係での活かし方
[この人の特性を踏まえた具体的アドバイス100文字以上]

### 📋 今週の処方箋
1. **[超具体的な行動提案]**: [なぜこれが効果的か]
2. **[超具体的な行動提案]**: [なぜこれが効果的か]
3. **[超具体的な行動提案]**: [なぜこれが効果的か]

この分析があなたの自己理解と成長のお役に立てれば幸いです。"""

        analysis_prompt = f"""以下の10問の回答を分析してください：

{responses_text}

この人の回答の具体性・言葉選び・エピソードから、完全個別化された診断を実行してください。
一般論は絶対に避け、この人だけの固有パターンを特定してください。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": analysis_prompt}
        ]

        logger.info("Calling OpenAI API with gpt-4o-mini...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_completion_tokens=3000,  # ← 修正：max_tokens から変更
            temperature=0.8
        )
        
        result = response.choices[0].message.content
        logger.info(f"✅ GPT analysis completed successfully! Result length: {len(result)} chars")
        return result

    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR in analyze_responses: {type(e).__name__}: {str(e)}", exc_info=True)
        return f"[分析エラー発生]\nエラー種類: {type(e).__name__}\nエラー内容: {str(e)}\n\n申し訳ございません。技術的な問題が発生しました。"

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
        
        share_message = """🎉 診断完了！

この診断結果はいかがでしたか？
当たっていると感じた部分があれば、ぜひ友達にもシェアしてみてください！

🔄 新しい診断: 「診断開始」
📤 友達に教える: この診断を友達にもおすすめしてください！

あなたの自己理解と成長のお役に立てれば幸いです ✨"""
        
        line_bot_api.push_message(user_id, TextSendMessage(text=share_message))
        logger.info(f"✅ Diagnosis result sent to {user_id}")
    except Exception as e:
        logger.error(f"Error in send_diagnosis_result: {e}")

@app.get("/")
async def root():
    return {"status": "ok", "message": "AI Diagnosis Bot Running"}

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "line_token": bool(LINE_CHANNEL_ACCESS_TOKEN),
        "line_secret": bool(LINE_CHANNEL_SECRET),
        "openai_key": bool(OPENAI_API_KEY)
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
