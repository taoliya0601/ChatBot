import Events
from Models.Plugins import *
from ..gocqOnQQ.CQHTTP_Protocol.CQHTTP_Protocol import CQHTTP_Protocol
from ..gocqOnQQ.QQevents.NoticeEvent import GroupMessageRecall, PersonMessageRecall


@register(
    description="撤回消息监听", version="1.0.0", author="For_Lin0601", priority=101
)
class RecalleEventPlugin(Plugin):

    @on(QQ_friend_recall)
    def on_qq_friend_recall(self, event: EventContext, **kwargs):
        config = self.emit(Events.GetConfig__)
        message: PersonMessageRecall = kwargs["QQevents"]
        event.prevent_postorder()

        # 忽略自身消息
        if message.user_id == config.qq:
            return
        if message.user_id in config.banned_person_list:
            return

        cqhttp: CQHTTP_Protocol = self.emit(Events.GetCQHTTP__)
        text = cqhttp.getMessage(message.message_id)
        cqhttp.sendPersonMessage(
            message.user_id, f"{config.message_recall_message}\n{text.message}"
        )

    @on(QQ_group_recall)
    def on_qq_group_recall(self, event: EventContext, **kwargs):
        config = self.emit(Events.GetConfig__)
        message: GroupMessageRecall = kwargs["QQevents"]
        event.prevent_postorder()
        if not config.quote_qq_group:
            return
        if message.group_id not in config.response_rules:
            return
        if message.group_id in config.banned_group_list:
            return
        if message.user_id in config.banned_person_list:
            return
        cfg = config.response_rules[message.group_id]
        if (
            (not cfg["at"])
            and cfg["prefix"] == []
            and cfg["regexp"] == []
            and cfg["random_rate"] == 0.0
        ):
            return
        # 忽略自身消息
        if message.user_id == config.qq:
            return

        cqhttp: CQHTTP_Protocol = self.emit(Events.GetCQHTTP__)
        text = cqhttp.getMessage(message.message_id)
        cqhttp.sendGroupMessage(
            message.group_id, f"{config.message_recall_message}\n{text.message}"
        )
