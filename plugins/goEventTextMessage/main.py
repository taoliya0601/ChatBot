
import random
import re
import time
from func_timeout import FunctionTimedOut, func_set_timeout


import Events
from .Events import *
from Models.Plugins import *

from ..gocqOnQQ.entities.components import At, Plain
from ..gocqOnQQ.CQHTTP_Protocol.CQHTTP_Protocol import CQHTTP_Protocol
from ..gocqOnQQ.QQevents.MessageEvent import PersonMessage, GroupMessage


@register(
    description="文本消息监听",
    version="1.0.0",
    author="For_Lin0601",
    priority=100
)
class TextMessageEventPlugin(Plugin):

    miss_seconds_dict: dict
    """由于go-cq内部问题, 在长时间不对话后的第一次对话可能会附带历史记录的最后一条对话

    故在此判断如果两条消息间隔少于1秒, 则忽略前面那条消息

    `{session_name: int(time.time())}`
    """

    processing = set()
    """排队列表"""

    @on(PluginsLoadingFinished)
    def first_init(self, event: EventContext,  **kwargs):
        self.miss_seconds_dict = {}
        self.processing = set()

    @on(PluginsReloadFinished)
    def get_config(self, event: EventContext,  **kwargs):
        self.miss_seconds_dict = self.get_reload_config(
            "miss_seconds_dict", default={})
        self.processing = self.get_reload_config("processing", default=set())

    def on_reload(self):
        self.set_reload_config("miss_seconds_dict", self.miss_seconds_dict)
        self.set_reload_config("processing", self.processing)

    @on(QQ_private_message)
    def check_cmd_and_chat_with_gpt(self, event: EventContext,  **kwargs):
        self.config = self.emit(Events.GetConfig__)
        message: PersonMessage = kwargs["QQevents"]

        # 忽略自身消息
        if message.user_id == self.config.qq:
            return

        # 此处只处理纯文本消息
        if message.message[0].type != "Plain":
            return

        event.prevent_postorder()

        # 检查发送方是否被禁用
        if self.is_banned("person", message.user_id):
            logging.debug(f"根据禁用列表忽略[person_{message.user_id}]的消息")
            return

        if self.emit(QQPersonMessageReceived) is False:
            logging.debug(f"根据插件忽略[person_{message.user_id}]的消息")
            return

        self.cqhttp: CQHTTP_Protocol = self.emit(Events.GetCQHTTP__)

        # 若有附加消息, 给出警告
        check_length = len(message.message) != 1

        msg: str = message.message[0].text.strip()

        if len(msg.replace(" ", "")) == 0:
            self.cqhttp.sendPersonMessage(
                message.user_id, "[bot]warinig: 不能发送空消息",
                auto_escape=True
            )
            return

        def time_ctrl_wrapper():
            tmp_id = []
            for _ in range(self.config.retry_times + 1):
                try:
                    @func_set_timeout(self.config.process_message_timeout)
                    def _time_crtl():
                        self.process_message(
                            "person", message.temp_source if message.temp_source else message.user_id,
                            msg, message, message.user_id, check_length
                        )
                    _time_crtl()
                    break
                except FunctionTimedOut:
                    session_name = "{}_{}".format(
                        "person", message.temp_source if message.temp_source else message.user_id)
                    self.processing.discard(session_name)
                    logging.warning(f"{message.user_id}: 超时, 重试中(第{_+1}次)")
                    tmp_id.append(self.cqhttp.sendPersonMessage(
                        message.user_id, f"[bot]warinig: 超时, 重试中(第{_+1}次)",
                        auto_escape=True
                    ).message_id)
            else:
                for id_ in tmp_id:
                    self.cqhttp.recall(id_)
        if self.is_admin(group_id=message.user_id):
            self.emit(Events.SubmitAdminTask__, fn=time_ctrl_wrapper)
        else:
            self.emit(Events.SubmitUserTask__, fn=time_ctrl_wrapper)

    @on(QQ_group_message)
    def check_cmd_and_chat_with_gpt(self, event: EventContext,  **kwargs):
        self.config = self.emit(Events.GetConfig__)
        if not self.config.quote_qq_group:
            return

        message: GroupMessage = kwargs["QQevents"]

        # 忽略自身消息
        if message.user_id == self.config.qq:
            return

        event.prevent_postorder()

        # 检查发送方是否被禁用
        if self.is_banned("group", message.group_id):
            logging.debug(f"根据禁用列表忽略[group_{message.group_id}]的消息")
            return

        self.cqhttp: CQHTTP_Protocol = self.emit(Events.GetCQHTTP__)

        # 判断群是否符合响应规则
        response_rules = self.config.response_rules.get(
            str(message.group_id),
            self.config.response_rules["default"]
        )

        if response_rules.get("at", False) and \
            message.message[0].type == "At" and \
                message.message[0].qq == str(self.config.qq):  # 符合at响应规则
            message.message = message.message[1:]
        elif message.message[0].type == "Plain":
            msg = message.message[0].text
            for prefix in response_rules.get("prefix", []):
                if msg.startswith(prefix):  # 符合prefix响应规则
                    break
            else:
                for regexp in response_rules.get("regexp", []):
                    if re.search(regexp, msg):  # 符合regexp响应规则
                        break
                else:
                    # random_rate字段随机值0.0-1.0
                    if random.random() >= response_rules.get("random_rate", 0.0):
                        logging.debug(f"根据规则忽略 {message.user_id}: {msg}")
                        return
        else:
            return

        # 若有附加消息, 给出警告
        check_length = len(message.message) != 1

        msg: str = message.message[0].text.strip()

        if len(msg.replace(" ", "")) == 0:
            self.cqhttp.sendGroupMessage(
                message.group_id, [
                    Plain(text="[bot]warning: "),
                    At(qq=message.user_id),
                    Plain(text="[bot]warinig: 不能发送空消息")
                ])
            return

        def time_ctrl_wrapper():
            tmp_id = []
            for _ in range(self.config.retry_times + 1):
                try:
                    @func_set_timeout(self.config.process_message_timeout)
                    def _time_crtl():
                        self.process_message(
                            "group", message.group_id,
                            msg, message, message.user_id, check_length
                        )
                    _time_crtl()
                    break
                except FunctionTimedOut:
                    session_name = "{}_{}".format("group", message.group_id)
                    self.processing.discard(session_name)
                    logging.warning(f"{message.user_id}: 超时, 重试中(第{_+1}次)")
                    tmp_id.append(self.cqhttp.sendPersonMessage(
                        message.user_id, f"[bot]warinig: 超时, 重试中(第{_+1}次)",
                        auto_escape=True
                    ).message_id)
            else:
                for id_ in tmp_id:
                    self.cqhttp.recall(id_)
        if self.is_admin(group_id=message.user_id):
            self.emit(Events.SubmitAdminTask__, fn=time_ctrl_wrapper)
        else:
            self.emit(Events.SubmitUserTask__, fn=time_ctrl_wrapper)

    def is_admin(self, group_id: int):
        """检查发送方是否为管理员"""
        return group_id in self.config.admin_list

    def is_banned(self, launcher_type: str, group_id: int):
        """检查发送方是否被禁用"""
        if launcher_type == "group":
            return group_id in self.config.banned_group_list
        return group_id in self.config.banned_person_list

    def process_message(
            self,
            launcher_type: str,
            group_id: int,
            text_message: str,
            message_chain: list,
            sender_id: int,
            check_length: bool
    ) -> None:
        """处理消息

        :param launcher_type: 发起对象类型
        :param group_id: 发起对象ID(可能为群号, 或临时会话)
        :param text_message: 消息文本
        :param message_chain: 消息原文
        :param sender_id: 发送者ID
        :param check_length: 是否为纯文本消息

        :return: None
        """
        session_name = "{}_{}".format(launcher_type, group_id)

        logging.info(f"收到消息[{session_name}]: {text_message}")

        if session_name in self.miss_seconds_dict:
            logging.warning("消息疑似重复(在一秒内连续收到两条消息, 为go-cq内部错误, 在此忽略前一条)" +
                            f"[{session_name}]: {text_message}")
            del self.miss_seconds_dict[session_name]
        else:
            now = int(time.time())
            self.miss_seconds_dict[session_name] = now
            time.sleep(0.5)
            if session_name not in self.miss_seconds_dict:
                return
            del self.miss_seconds_dict[session_name]

        # 触发命令
        if text_message[0] in ["!", "！"]:
            self.emit(GetQQPersonCommand if launcher_type == "person" else GetQQGroupCommand,
                      message=text_message[1:],
                      message_chain=message_chain,
                      group_id=group_id,
                      sender_id=sender_id,
                      is_admin=self.is_admin(sender_id)
                      )
            return

        # 限速策略
        logging.debug(f"当前排队列表: {self.processing=}")
        if session_name in self.processing:
            if launcher_type == "person":
                self.cqhttp.sendPersonMessage(
                    sender_id, self.config.message_drop_message,
                    group_id=group_id if group_id != sender_id else None,
                    auto_escape=True)
            return
        self.processing.add(session_name)
        try:
            tmp_msg = "[bot] 收到消息, " + \
                (f"当前{len(self.processing)-1}人正在排队" if len(self.processing)
                 > 1 else "当前无人排队, 消息处理中")
            if check_length:
                tmp_msg += f"\n!非纯文本消息!只取最前面文本为处理内容, 忽略后面特殊类型信息!"
            if launcher_type == "person":
                tmp_id = self.cqhttp.sendPersonMessage(
                    sender_id,  tmp_msg,
                    group_id=group_id if group_id != sender_id else None,
                    auto_escape=True).message_id
            else:
                tmp_id = self.cqhttp.sendGroupMessage(group_id, [
                    At(qq=sender_id), Plain(text=tmp_msg)
                ]).message_id

            # 处理消息
            reply = self.emit(Events.GetOpenAi__).request_completion(
                session_name, text_message)

            if launcher_type == "person":
                self.cqhttp.sendPersonMessage(
                    sender_id, reply,
                    group_id=group_id if group_id != sender_id else None,
                    auto_escape=True)
            else:
                self.cqhttp.sendGroupMessage(group_id, [
                    At(qq=sender_id), Plain(text=reply)
                ])
        except Exception as e:
            logging.error(e)
            if launcher_type == "person":
                self.cqhttp.NotifyAdmin(
                    f"[bot]err: [{session_name}]处理消息出现错误:\n{e}")
                self.cqhttp.sendPersonMessage(
                    sender_id, f"[bot]err: 处理消息出现错误, 请尝试联系管理员解决:\n{e}",
                    group_id=group_id if group_id != sender_id else None,
                    auto_escape=True)
        finally:
            self.processing.discard(session_name)

        if not self.cqhttp.recall(tmp_id):
            logging.warning(f"{session_name}: {tmp_id}消息撤回失败")
