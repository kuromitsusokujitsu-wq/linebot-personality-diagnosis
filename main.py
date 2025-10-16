from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai
import os
import json
import uvicorn

# 環境変数（実際のデプロイ時に設定）
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# LINE Bot APIの初期化
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# OpenAI APIの初期化
openai.api_key = OPENAI_API_KEY
client = openai.OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI()

# ユーザーの回答を保存するための辞書
user_responses = {}

# 革新的10問の質問設計
QUESTIONS = {
    1: {
        "question": "🤔 **質問1/10【認知構造】**\n\n最近、重要な決断をした体験について、その時の思考プロセスを具体的に教えてください。何を考え、何を重視し、最終的にどう判断したかを詳しく。",
        "example": "📝 **記入例**\n先月、転職するかどうかで悩んでいました。まず現在の仕事の不満点をリストアップし、転職先の条件と比較しました。でも最終的な決め手は「直感的にワクワクするか」でした。論理的に考えても、最後は感情が動かないと決断できないタイプだと気づきました...\n\n💡 **ポイント**: 具体的な状況・思考プロセス・判断基準・振り返りを詳しく！"
    },
    2: {
        "question": "📚 **質問2/10【認知構造】**\n\n新しいことを学ぶとき、どんなアプローチを取りますか？学習方法、動機、継続の仕方について、あなたなりのやり方を教えてください。",
        "example": "📝 **記入例**\n興味を持った分野は、まずYouTubeで概要を掴んでから本を読みます。一人で黙々とやるより、同じ興味を持つ人とディスカッションする方が理解が深まります。完璧を求めすぎて挫折することが多いので、最近は「まず60%の理解で良し」と割り切るようにしています...\n\n💡 **ポイント**: 学習スタイル・モチベーション・継続のコツを具体的に！"
    },
    3: {
        "question": "😰 **質問3/10【感情構造】**\n\nストレスや困難な状況に直面したとき、どんな感情が湧き、どう対処していますか？最近の具体的な経験も含めて教えてください。",
        "example": "📝 **記入例**\n仕事でトラブルが起きると、まず「なんで私が...」という怒りが湧きます。でもその後すぐに「どうしよう」という不安に変わります。対処法としては、一旦深呼吸して問題を紙に書き出し、優先順位をつけて一つずつ解決していきます。友人に愚痴を聞いてもらうのも大切なプロセスです...\n\n💡 **ポイント**: 感情の変化・対処方法・具体的なエピソードを詳しく！"
    },
    4: {
        "question": "✨ **質問4/10【感情構造】**\n\nあなたが最も充実感や喜びを感じる瞬間について教えてください。それはなぜそう感じるのか、理由も含めて。",
        "example": "📝 **記入例**\n後輩に仕事を教えて、その人が「わかりました！」と目を輝かせる瞬間が最高に嬉しいです。自分の知識や経験が誰かの役に立っている実感と、相手の成長を間近で見られる特別感があります。一人で何かを達成するより、誰かと一緒に成長できる体験の方に深い喜びを感じます...\n\n💡 **ポイント**: 具体的なシーン・なぜ嬉しいのか・価値観との関係を詳しく！"
    },
    5: {
        "question": "👥 **質問5/10【行動構造】**\n\n人間関係で困った経験について、その時の状況と、あなたがとった行動、そしてその行動を選んだ理由を教えてください。",
        "example": "📝 **記入例**\n同僚との意見対立で職場の雰囲気が悪くなった時、私は直接話し合いを提案しました。周りは「触らぬ神に祟りなし」という感じでしたが、このままだと皆が気を遣い続けることになると思ったからです。結果的に誤解が解けて関係が改善しました。対立を避けるより、建設的に解決したい性格だと思います...\n\n💡 **ポイント**: 具体的な状況・とった行動・選択理由・結果への考察を詳しく！"
    },
    6: {
        "question": "🎯 **質問6/10【価値観構造】**\n\nあなたが「これだけは譲れない」と思うことは何ですか？それはなぜ大切で、どんな経験からそう思うようになったかも教えてください。",
        "example": "📝 **記入例**\n「人を裏切らない」ことは絶対に譲れません。学生時代に親友だと思っていた人に陰で悪口を言われていたことがあり、信頼関係の大切さを痛感しました。それ以来、小さな約束でも必ず守るし、人の秘密は絶対に漏らしません。信頼は築くのに時間がかかるけど、失うのは一瞬だと学びました...\n\n💡 **ポイント**: 譲れないこと・大切な理由・形成された経験を詳しく！"
    },
    7: {
        "question": "🌟 **質問7/10【価値観構造】**\n\n人生で最も大切にしたい価値観や生き方について教えてください。理想的な人生とはどんなものか、あなたの考えを聞かせてください。",
        "example": "📝 **記入例**\n「自分らしく、でも人の役に立つ」生き方を大切にしたいです。無理して他人に合わせるのではなく、自分の特性を活かして社会貢献できる人生が理想です。派手な成功より、身近な人から「ありがとう」と言われる機会の多い人生の方が価値があると思います。バランスを取りながら、充実感のある毎日を送りたいです...\n\n💡 **ポイント**: 大切な価値観・理想の人生像・なぜそう思うのかを詳しく！"
    },
    8: {
        "question": "🚀 **質問8/10【自己物語】**\n\n5年後、どんな自分になっていたいですか？その理想の自分になるために、今何を大切にしていますか？",
        "example": "📝 **記入例**\n5年後は、専門分野で一定の地位を築きつつ、後輩の育成にも力を入れている自分でいたいです。今は技術スキルの向上はもちろん、人とのコミュニケーション能力も意識的に鍛えています。理想の自分になるには、目の前のことを丁寧にやりつつ、長期的な視点も持ち続けることが大切だと思っています...\n\n💡 **ポイント**: 具体的な理想像・そのための現在の取り組み・成長への考えを詳しく！"
    },
    9: {
        "question": "⏰ **質問9/10【時間軸構造】**\n\n過去の自分と比べて、今いちばん変わったと思う点は？その変化をどう捉えていますか？",
        "example": "📝 **記入例**\n学生時代は人の目ばかり気にしていましたが、今は自分の価値観を大切にするようになりました。特に30歳を過ぎてから「他人の期待に応える人生」から「自分らしい人生」にシフトチェンジした感覚があります。この変化は良いことだと思っていて、もっと自分軸を大切にしていきたいです...\n\n💡 **ポイント**: 具体的な変化・いつからか・変化への評価・きっかけを詳しく！"
    },
    10: {
        "question": "👨‍👩‍👧‍👦 **質問10/10【他者視点構造】**\n\n親しい友人があなたを他の人に紹介するとき、何と言うと思いますか？また、それは自分が思う自分の特徴と同じですか？",
        "example": "📝 **記入例**\n友人は「彼女は一見おとなしそうだけど、実はすごく芯が強くて、困った時に頼りになる人」と言うと思います。私自身は「優柔不断で心配性」だと思っているので、友人の方が私を強く見てくれているのかもしれません。実際、相談される機会は多いので、案外当たっているかも...\n\n💡 **ポイント**: 友人の紹介予想・自己認識との違い・その考察を詳しく！"
    }
}

@app.post("/webhook")
async def webhook(request: Request):
    signature = request.headers.get('X-Line-Signature', '')
    body = await request.body()
    
    try:
        handler.handle(body.decode('utf-8'), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    return {"status": "ok"}

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()
    
    # ユーザーデータの初期化
    if user_id not in user_responses:
        user_responses[user_id] = {
            "current_question": 0,
            "answers": {},
            "completed": False
        }
    
    user_data = user_responses[user_id]
    
    # 診断開始
    if user_message in ["診断", "start", "開始", "診断開始"] or user_data["current_question"] == 0:
        start_diagnosis(user_id)
        return
    
    # 診断完了後の処理
    if user_data["completed"]:
        reply_message = "診断は既に完了しています。新しい診断を始める場合は「診断開始」と送信してください。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_message))
        return
    
    # 回答の処理
    if user_data["current_question"] > 0:
        process_answer(user_id, user_message, event.reply_token)

def start_diagnosis(user_id):
    """診断開始"""
    user_responses[user_id] = {
        "current_question": 1,
        "answers": {},
        "completed": False
    }
    
    welcome_message = """🎯 **AIパーソナル診断へようこそ！**

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
    
    line_bot_api.push_message(user_id, TextSendMessage(text=welcome_message))
    
    # 最初の質問を送信
    send_question(user_id, 1)

def send_question(user_id, question_num):
    """質問を送信"""
    if question_num > 10:
        return
    
    question_data = QUESTIONS[question_num]
    
    # 質問文を送信
    line_bot_api.push_message(
        user_id, 
        TextSendMessage(text=question_data["question"])
    )
    
    # 記入例を送信
    line_bot_api.push_message(
        user_id, 
        TextSendMessage(text=question_data["example"])
    )
    
    # 励ましメッセージを送信
    encouragement = "💪 詳しく教えていただくほど、より精密で個人的な診断が可能になります。遠慮なく、思ったことを自由に表現してください！"
    line_bot_api.push_message(
        user_id, 
        TextSendMessage(text=encouragement)
    )

def process_answer(user_id, answer, reply_token):
    """回答を処理"""
    user_data = user_responses[user_id]
    current_q = user_data["current_question"]
    
    # 回答を保存
    user_data["answers"][current_q] = answer
    
    if current_q < 10:
        # 次の質問へ
        user_data["current_question"] = current_q + 1
        
        # 受け答えメッセージ
        thanks_message = f"✅ 質問{current_q}の回答ありがとうございます！\n\n続いて質問{current_q + 1}です。"
        line_bot_api.reply_message(reply_token, TextSendMessage(text=thanks_message))
        
        # 次の質問を送信
        send_question(user_id, current_q + 1)
    else:
        # 全質問完了 - 診断実行
        user_data["completed"] = True
        
        completion_message = "🎉 全ての質問にお答えいただき、ありがとうございました！\n\n分析中です...少しお待ちください。"
        line_bot_api.reply_message(reply_token, TextSendMessage(text=completion_message))
        
        # 診断分析実行
        diagnosis_result = analyze_responses(user_data["answers"])
        
        # 結果送信
        send_diagnosis_result(user_id, diagnosis_result)

def analyze_responses(answers):
    """革命的AI診断分析"""
    try:
        # 回答をテキスト形式に変換
        responses_text = ""
        for q_num, answer in answers.items():
            responses_text += f"質問{q_num}: {answer}\n\n"
        
        # 革命的分析プロンプト
        system_prompt = """あなたは心理学・言語学・認知科学の統合的専門家「Dr. Insight Genesis」です。

【ULTIMATE MISSION】
10の自由回答から、この人の「心理的DNA」を完全解読せよ。
既存診断では不可能な、完全個別化された人格分析を実行せよ。

【7層統合分析フレームワーク】
1. **認知構造**: 思考処理の独自パターン
2. **感情構造**: 感情の動き方・調整方法
3. **行動構造**: 対人・問題解決の行動特性
4. **価値観構造**: 判断基準の深層構造
5. **自己物語**: アイデンティティの核心
6. **時間軸構造**: 成長・変化への態度
7. **他者視点構造**: 自己認知の精度

【言語心理学分析】
- 語彙選択から見える価値観の重心
- 文体から読み取る思考の特徴
- 感情表現から判明する感情処理スタイル
- 時制使用から見える時間軸思考
- 抽象度から測定する思考レベル

【対比分析の活用】
質問9の回答から「自己概念の動態性」を特定し、
他の回答との整合性で「本質的変化 vs 表面的変化」を判別

【人称変化分析の活用】  
質問10の回答から「自己認知のズレ」を測定し、
「過小評価型 vs 過大評価型 vs 適正評価型」を判定

【出力要件】
- この人だけに当てはまる固有洞察
- 「なんで私のことそんなに知ってるの？」レベルの的中感
- 友達に教えたくなる驚きの発見
- 実生活で即活用できる具体的アドバイス

以下のフォーマットで出力してください：

🎯 **診断完了！**

【あなたの診断結果】

## 🎭 「○○○な○○○」

### 💫 あなたの思考構造
（認知パターンの個別分析）

### 💝 感情のクセ
（感情処理の独自パターン）

### 🌟 価値観の核
（判断基準の深層構造）

### 📖 物語の型
（アイデンティティの特徴）

### 💪 強みTop3
1. **○○**: ○○
2. **○○**: ○○
3. **○○**: ○○

### ⚠️ 注意点Top3
1. **○○**: ○○
2. **○○**: ○○
3. **○○**: ○○

### 💡 活かし方ガイド

#### 🧩 仕事での活かし方
（具体的アドバイス）

#### 💞 恋愛での活かし方
（具体的アドバイス）

#### 🧑‍🤝‍🧑 対人関係での活かし方
（具体的アドバイス）

### 📋 今週の処方箋
1. **○○**: ○○
2. **○○**: ○○
3. **○○**: ○○

この分析があなたの自己理解と成長のお役に立てれば幸いです。"""

        analysis_prompt = f"""
{responses_text}

上記の10問の回答を分析し、この人の完全個別化された診断を実行してください。
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": analysis_prompt}
        ]

        # GPT-5-nano使用（コスト最適化）
        response = client.chat.completions.create(
            model="gpt-5-nano",  # 革新的モデル
            messages=messages,
            max_tokens=2000,
            temperature=0.7
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"診断分析エラー: {e}")
        return generate_fallback_diagnosis()

def generate_fallback_diagnosis():
    """フォールバック診断"""
    return """🎯 **診断完了！**

【あなたの診断結果】

## 🎭 「思慮深いバランサー」

### 💫 あなたの思考構造
あなたは物事を多角的に検討し、慎重に判断を下すタイプです。感情と論理のバランスを取りながら、周囲との調和も大切にする思考パターンを持っています。

### 💝 感情のクセ
感情をため込みがちですが、信頼できる人には素直に表現できます。ストレス時は一人の時間を大切にし、内省を通じて解決策を見つけようとします。

### 🌟 価値観の核
誠実さと信頼関係を何より重視します。自分らしさを保ちながらも、他者との良好な関係を築くことに価値を見出しています。

### 📖 物語の型
着実な成長を重ねながら、自分なりのペースで人生を歩んでいます。大きな変化より、継続的な改善を通じて理想に近づこうとしています。

### 💪 強みTop3
1. **バランス感覚**: 多様な視点を統合する能力
2. **共感力**: 他者の気持ちを理解し寄り添う力
3. **継続力**: 地道に努力を積み重ねる力

### ⚠️ 注意点Top3
1. **完璧主義**: 高すぎる基準で自分を追い込むことがある
2. **優柔不断**: 慎重すぎて決断が遅れることがある
3. **自己犠牲**: 他者を優先しすぎて自分を後回しにする傾向

### 💡 活かし方ガイド

#### 🧩 仕事での活かし方
チーム内の調整役として力を発揮できます。多様な意見をまとめ、建設的な解決策を見つける能力を活かしましょう。

#### 💞 恋愛での活かし方
相手の気持ちに寄り添える優しさが魅力です。自分の気持ちも素直に表現することで、より深い関係が築けるでしょう。

#### 🧑‍🤝‍🧑 対人関係での活かし方
聞き上手な特性を活かし、人の相談に乗ることで信頼関係を深めることができます。

### 📋 今週の処方箋
1. **小さな決断練習**: 日常の小さなことから即断即決を心がける
2. **感情表現**: 信頼できる人に今の気持ちを言葉で伝える
3. **自分時間**: 一人でリラックスできる時間を意識的に作る

この分析があなたの自己理解と成長のお役に立てれば幸いです。"""

def send_diagnosis_result(user_id, diagnosis_result):
    """診断結果を送信"""
    # 結果が長い場合は分割して送信
    max_length = 5000
    
    if len(diagnosis_result) <= max_length:
        line_bot_api.push_message(
            user_id, 
            TextSendMessage(text=diagnosis_result)
        )
    else:
        # 長文を分割
        parts = []
        current_part = ""
        
        lines = diagnosis_result.split('\n')
        for line in lines:
            if len(current_part + line + '\n') <= max_length:
                current_part += line + '\n'
            else:
                if current_part:
                    parts.append(current_part)
                current_part = line + '\n'
        
        if current_part:
            parts.append(current_part)
        
        # 分割された結果を順次送信
        for i, part in enumerate(parts):
            if i == 0:
                line_bot_api.push_message(user_id, TextSendMessage(text=part))
            else:
                line_bot_api.push_message(user_id, TextSendMessage(text=f"**続き {i+1}**\n\n{part}"))
    
    # 完了メッセージとシェア促進
    share_message = """🎉 **診断完了！**

この診断結果はいかがでしたか？
当たっていると感じた部分があれば、ぜひ友達にもシェアしてみてください！

🔄 **新しい診断**: 「診断開始」
📤 **友達に教える**: この診断を友達にもおすすめしてください！

あなたの自己理解と成長のお役に立てれば幸いです ✨"""
    
    line_bot_api.push_message(user_id, TextSendMessage(text=share_message))

@app.get("/")
async def root():
    return {"message": "AI Personality Diagnosis Bot is running!"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
