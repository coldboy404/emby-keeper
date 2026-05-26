import re

from embykeeper.runinfo import RunStatus

from ._templ_ai import TemplateAICheckin


class MooncakeAICheckin(TemplateAICheckin):
    name = "月饼 AI"
    bot_username = "Moonkkbot"
    bot_checked_keywords = ["今日已签到"]
    bot_too_many_tries_fail_keywords = [
        "已尝试",
        "过多",
        "次数过多",
        "明天再试",
        "错误",
        "失败",
        "不正确",
        "验证码错误",
        "答案错误",
    ]
    llm_button_match_threshold = 95
    llm_prompt = (
        "你在帮助月饼站签到。图片中会出现一个单个阿拉伯数字验证码。"
        "请只识别验证码图片中最大、最深色、最像前景主体的那个数字，"
        "忽略按钮数字、返回按钮、聊天界面文字、背景噪点、干扰线和圆圈。"
        "只输出验证码对应的单个数字按钮；如果不确定，不要猜。"
    )

    uncertain_answer_keywords = (
        "可能",
        "也许",
        "大概",
        "应该",
        "疑似",
        "像是",
        "看起来",
        "不确定",
        "无法判断",
        "不清楚",
        "maybe",
        "probably",
        "uncertain",
        "unknown",
    )

    def extract_answer(self, content):
        answer = super().extract_answer(content)
        if not answer:
            return None

        normalized = answer.strip()
        if any(keyword in normalized.lower() for keyword in self.uncertain_answer_keywords):
            return None

        digits = re.findall(r"\d", normalized)
        unique_digits = set(digits)
        if len(unique_digits) != 1:
            return None
        if normalized != digits[0]:
            # Accept harmless wrappers only when they mention exactly one digit,
            # but reject any response that also references buttons/options.
            if any(keyword in normalized for keyword in ("按钮", "选项", "候选", "返回")):
                return None
        return digits[0]

    async def retry(self):
        """Mooncake burns the daily chance after a wrong captcha click.

        Do not resend the checkin command or press any fallback/return button on
        LLM uncertainty, click failures, or captcha error responses.  The bot may
        present two captcha rounds during one checkin, but each round only has one
        safe click opportunity; stopping is safer than consuming the chance.
        """
        self.log.warning("月饼 AI 签到停止: 当前流程不允许自动重试或返回, 请人工确认后再处理.")
        await self.finish(RunStatus.FAIL, "月饼 AI 验证失败, 已停止自动重试")

    def match_button(self, answer, options):
        """Only click a single explicit digit answer for Mooncake.

        The bot presents single-digit numeric buttons.  Fuzzy matching can turn
        vague model output into a wrong click, which quickly burns the daily
        retry budget.  Be conservative: click only when the model response
        contains exactly one certain digit that is present in the numeric options.
        """
        numeric_options = {option for option in options if re.fullmatch(r"\d", option)}
        answer = (answer or "").strip()
        digit = None
        if not any(keyword in answer.lower() for keyword in self.uncertain_answer_keywords):
            numeric_digits = re.findall(r"\d", answer)
            unique_digits = set(numeric_digits)
            digit = numeric_digits[0] if len(unique_digits) == 1 else None
        if digit and digit in numeric_options:
            return digit
        self.log.warning(
            f'月饼 AI 签到暂不点击: 图像模型结果 "{answer}" 未给出唯一确定数字答案, '
            f"候选数字按钮: {sorted(numeric_options)}."
        )
        return None
