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
        "你在帮助月饼站签到。图片中会出现一个数字验证码，"
        "下方按钮里包含 0 到 9 以及其他功能按钮。"
        "请只选择验证码对应的那个数字按钮，不要选择返回或其他功能键。"
    )

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
        contains exactly one digit that is present in the numeric options.
        """
        numeric_options = {option for option in options if re.fullmatch(r"\d", option)}
        digits = re.findall(r"\d", answer or "")
        unique_digits = [digit for digit in dict.fromkeys(digits) if digit in numeric_options]
        if len(unique_digits) == 1:
            return unique_digits[0]
        self.log.warning(
            f'月饼 AI 签到暂不点击: 图像模型结果 "{answer}" 未给出唯一数字答案, '
            f"候选数字按钮: {sorted(numeric_options)}."
        )
        return None
