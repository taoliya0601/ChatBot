
import random
import re
from func_timeout import FunctionTimedOut, func_set_timeout


import Events
from plugins.wcferry.Events import Wx_msg
from .Events import *
from Models.Plugins import *

from wcferry import Wcf, WxMsg


@register(
    description="微信文本消息监听",
    version="1.0.0",
    author="For_Lin0601",
    priority=150,
    # enabled=False
)
class WxChatTextMessageEventPlugin(Plugin):

    @on(PluginsLoadingFinished)
    def first_init(self, event: EventContext,  **kwargs):
        self.processing = set()

    @on(PluginsReloadFinished)
    def get_config(self, event: EventContext,  **kwargs):
        self.processing = self.get_reload_config("processing", default=set())

    def on_reload(self):
        self.set_reload_config("processing", self.processing)

    @on(Wx_msg)
    def check_cmd_and_chat_with_gpt(self, event: EventContext,  **kwargs):
        message: WxMsg = kwargs["Wx_msg"]
        # 此处只处理纯文本消息
        if not message.is_text():
            return

        self.wcf: Wcf = self.emit(Events.GetWCF__)
        # 忽略自身消息
        if message.sender == self.wcf.self_wxid:
            return

        event.prevent_postorder()
        self.config = self.emit(Events.GetConfig__)

        # 检查发送方是否被禁用
        if self.is_banned(message.sender):
            logging.debug(f"根据禁用列表忽略[{message.sender}]的消息")
            return

        # 判断群是否符合响应规则
        if message.roomid:
            if not self.config.quote_wx_group:
                logging.debug(f"忽略群消息[{message.roomid}]")
                return
            response_rules = self.config.wx_response_rules.get(
                message.roomid,
                self.config.wx_response_rules["default"]
            )

            if not (response_rules.get("at", False) and
                    message.is_at(self.wcf.self_wxid)):  # 符合at响应规则
                msg = message.content.strip()
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
                            logging.debug(f"根据规则忽略 {message.sender}: {msg}")
                            return

        if self.emit(WXMessageReceived) is False:
            logging.debug(f"根据插件忽略[{message.sender}]的消息")
            return

        msg: str = message.content.strip()

        if len(msg.replace(" ", "")) == 0:
            self.wcf.send_text(
                "[bot]warinig: 不能发送空消息", message.roomid if message.roomid else message.sender
            )
            return

        def time_ctrl_wrapper():
            for _ in range(self.config.wx_retry_times + 1):
                try:
                    @func_set_timeout(self.config.process_message_timeout)
                    def _time_crtl():
                        self.process_message(
                            msg, message, message.sender, message.roomid, kwargs["is_admin"])
                    _time_crtl()
                    break
                except FunctionTimedOut:
                    session_name = "wx_{}".format(
                        message.roomid if message.roomid else message.sender)
                    self.processing.discard(session_name)
                    logging.warning(f"{message.sender}: 超时, 重试中(第{_+1}次)")
                    self.wcf.send_text(
                        f"[bot]warinig: 超时, 重试中(第{_+1}次)", message.sender)
        if kwargs["is_admin"]:
            self.emit(Events.SubmitAdminTask__, fn=time_ctrl_wrapper)
        else:
            self.emit(Events.SubmitUserTask__, fn=time_ctrl_wrapper)

    def is_banned(self, wxid: str):
        """检查发送方是否被禁用"""
        if wxid in self.config.wx_banned_list:
            return True
        for friend in self.wcf.get_contacts():
            if friend['code'] == wxid:
                if friend['code'] in self.config.wx_banned_list:
                    return True
                return False
        return False

    def process_message(
            self,
            text_message: str,
            message: list,
            sender: str,
            roomid: str = "",
            is_admin: bool = False
    ) -> None:
        """处理消息

        :param text_message: 消息文本
        :param message: WxMsg 数据存储类
        :param sender: 发送者ID
        :param roomid: (仅群消息有)群 id
        :param is_admin: 是否为管理员

        :return: None
        """
        session_name = "wx_{}".format(roomid if roomid else sender)

        logging.info(f"收到微信消息[{session_name}]: {text_message}")

        # 触发命令
        if text_message[0] in ["!", "！"]:
            self.emit(GetWXCommand,
                      command=text_message[1:],
                      message=message,
                      sender=sender,
                      roomid=roomid,
                      is_admin=is_admin
                      )
            return

        # 限速策略
        logging.debug(f"当前排队列表: {self.processing=}")
        if session_name in self.processing:
            self.wcf.send_text(
                self.config.message_drop_message, roomid if roomid else sender
            )
            return
        self.processing.add(session_name)
        try:
            # 处理消息
            reply = self.emit(Events.GetOpenAi__).request_completion(
                session_name, text_message)
            logging.info(f"回复微信消息[{session_name}]: {reply}")
            if roomid:
                friend_name = self.wcf.get_info_by_wxid(sender)['name']
                self.wcf.send_text(f"@{friend_name} {reply}", roomid, sender)
            else:
                self.wcf.send_text(reply, sender)
        except Exception as e:
            logging.error(e)
            self.wcf.send_text(
                f"[bot]err: [{session_name}]处理消息出现错误:\n{e}"), roomid if roomid else sender
            self.emit(Events.GetCQHTTP__).NotifyAdmin(
                f"[bot]err: 微信[{session_name}]处理消息出现错误:\n{e}")
        finally:
            self.processing.discard(session_name)
