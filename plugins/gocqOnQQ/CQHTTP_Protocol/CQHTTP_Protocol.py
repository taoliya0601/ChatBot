
import json
import logging
import threading
import time
import typing as T
import random

import requests

from Events import *
from Models.Plugins import Plugin
from ..event.models import BotMessage, Message, Anonymous, ForwardMessages
from ..entities import *
from ..entities.components import Node


class CQHTTP_Protocol(Plugin):
    """发送CQHTTP请求"""

    def __init__(self, http_url: str):
        self.http_url = http_url
        self.lock = threading.Lock()

    def _sent_post(self, url: str, data: dict = None) -> dict:
        """发送post请求"""
        with self.lock:
            response = requests.post(url, json=data)
            if response.status_code != 200:
                raise Exception(response.text)
            response = json.loads(response.text)
            if response["status"] == "async":
                logging.debug(
                    f"Network: post: {url=}, {data=}, 异步请求: {response=}")
            elif response["status"] == "failed":
                logging.error(
                    f"Network: 请求失败: post: {url=}, {data=}, {response}\n{response['msg']=}\n{response['wording']=}")
            else:
                logging.debug(f"Network: post: {url=}, {data=}, {response=}")
            return response

    def NotifyAdmin(self, message: T.Union[str, list]):
        for admin in self.emit(GetConfig__).admin_list:
            self.sendPersonMessage(admin, message)

    def sendPersonMessage(self,
                          user_id: int,
                          message: T.Union[str, list],
                          group_id: T.Optional[int] = None,
                          auto_escape: bool = False) -> T.Union[BotMessage, bool]:
        if isinstance(message, list):
            _message = ""
            for chain in message:
                _message += chain.toString()
            message = _message
        elif isinstance(message, str) and len(message) > 1000:
            msg = self.emit(ForwardMessage__, message=message)
            res = self.sendPersonForwardMessage(user_id, msg)
            if res is not False:
                return res
        logging.info(f"发送消息[person_{user_id}]: {message}")
        payload = {
            "user_id": user_id,
            "message": message,
            "auto_escape": auto_escape
        }
        if group_id:
            payload["group_id"] = group_id
        result = self._sent_post(
            f"{self.http_url}/send_private_msg", payload)
        if result["status"] == "ok":
            return BotMessage.model_validate(result["data"])
        return False

    def sendGroupMessage(self,
                         group_id: int,
                         message: T.Union[str, list],
                         auto_escape: bool = False) -> T.Union[BotMessage, bool]:
        if isinstance(message, list):
            _message = ""
            for chain in message:
                _message += chain.toString()
            message = _message
        elif isinstance(message, str) and len(message) > 1000:
            msg = self.emit(ForwardMessage__, message=message)
            res = self.sendGroupForwardMessage(group_id, msg)
            if res is not False:
                return res
        logging.info(f"发送消息[group_{group_id}]: {message}")
        result = self._sent_post(f"{self.http_url}/send_group_msg", {
            "group_id": group_id,
            "message": message,
            "auto_escape": auto_escape
        })
        if result["status"] == "ok":
            return BotMessage.model_validate(result["data"])
        return False

    def sendPersonForwardMessage(self,
                                 user_id: int,
                                 messages: list) -> T.Union[BotMessage, bool]:
        for i in range(len(messages)):
            if isinstance(messages[i], Node):
                messages[i] = messages[i].toDict()
        logging.info(f"发送合并消息[person_{user_id}]: {messages}")
        for _ in range(20):
            result = self._sent_post(f"{self.http_url}/send_private_forward_msg", {
                "user_id": user_id,
                "messages": messages
            })
            if result["status"] == "ok":
                return BotMessage.model_validate(result["data"])
            time.sleep(random.random() * 0.4 + 0.1)
        return False

    def sendGroupForwardMessage(self,
                                group_id: int,
                                messages: list) -> T.Union[BotMessage, bool]:
        for i in range(len(messages)):
            if isinstance(messages[i], Node):
                messages[i] = messages[i].toDict()
        logging.info(f"发送合并消息[group_{group_id}]: {messages}")
        for _ in range(20):
            result = self._sent_post(f"{self.http_url}/send_group_forward_msg", {
                "group_id": group_id,
                "messages": messages
            })
            if result["status"] == "ok":
                return BotMessage.model_validate(result["data"])
            time.sleep(random.random() * 0.4 + 0.1)
        return False

    def recall(self, message_id: int) -> bool:
        result = self._sent_post(f"{self.http_url}/delete_msg", {
            "message_id": message_id
        })
        if result["status"] == "ok":
            return True
        return False

    def getMessage(self, message_id: int) -> T.Union[Message, bool]:
        result = self._sent_post(f"{self.http_url}/get_msg", {
            "message_id": message_id
        })
        if result["status"] == "ok":
            return Message.model_validate(result["data"])
        return False

    def getForwardMessage(self, message_id: int) -> T.Union[ForwardMessages, bool]:
        result = self._sent_post(f"{self.http_url}/get_forward_msg", {
            "message_id": message_id
        })
        if result["status"] == "ok":
            return ForwardMessages.model_validate(result["data"])
        return False

    def getImage(self, file: str) -> T.Union[ImageFile, bool]:
        result = self._sent_post(f"{self.http_url}/get_image", {
            "file": file
        })
        if result["status"] == "ok":
            return ImageFile.model_validate(result["data"])
        return False

    def kick(self,
             group_id: int,
             user_id: int,
             reject_add_request: bool = False) -> bool:
        result = self._sent_post(f"{self.http_url}/set_group_kick", {
            "group_id": group_id,
            "user_id": user_id,
            "reject_add_request": reject_add_request
        })
        if result["status"] == "ok":
            return True
        return False

    def mute(self,
             group_id: int,
             user_id: int,
             duration: int = 30 * 60) -> bool:
        result = self._sent_post(f"{self.http_url}/set_group_ban", {
            "group_id": group_id,
            "user_id": user_id,
            "duration": duration
        })
        if result["status"] == "ok":
            return True
        return False

    def unmute(self, group_id: int, user_id: int) -> bool:
        return self.mute(group_id, user_id, 0)

    def muteAnonymous(self,
                      group_id: int,
                      flag: str,
                      duration: int = 30 * 60,
                      anonymous: Anonymous = None):  # TODO
        result = self._sent_post(f"{self.http_url}/set_group_anonymous_ban", {
            "group_id": group_id,
            "flag": flag,
            "duration": duration
        })
        if result["status"] == "ok":
            return True
        return False

    def muteAll(self,
                group_id: int,
                enable: bool = True) -> bool:
        result = self._sent_post(f"{self.http_url}/set_group_whole_ban", {
            "group_id": group_id,
            "enable": enable
        })
        if result["status"] == "ok":
            return True
        return False

    def setGroupAdmin(self,
                      group_id: int,
                      user_id: int,
                      enable: bool = True) -> bool:
        result = self._sent_post(f"{self.http_url}/set_group_admin", {
            "group_id": group_id,
            "user_id": user_id,
            "enable": enable
        })
        if result["status"] == "ok":
            return True
        return False

    def setGroupAnonymous(self,
                          group_id: int,
                          enable: bool = True) -> bool:  # TODO go-cqhttp 暂未支持
        result = self._sent_post(f"{self.http_url}/set_group_anonymous", {
            "group_id": group_id,
            "enable": enable
        })
        if result["status"] == "ok":
            return True
        return False

    def setGroupCard(self,
                     group_id: int,
                     user_id: int,
                     card: str = "") -> bool:
        result = self._sent_post(f"{self.http_url}/set_group_card", {
            "group_id": group_id,
            "user_id": user_id,
            "card": card
        })
        if result["status"] == "ok":
            return True
        return False

    def setGroupName(self,
                     group_id: int,
                     group_name: str) -> bool:
        result = self._sent_post(f"{self.http_url}/set_group_name", {
            "group_id": group_id,
            "group_name": group_name
        })
        if result["status"] == "ok":
            return True
        return False

    def leave(self,
              group_id: int,
              is_dismiss: bool = False) -> bool:
        result = self._sent_post(f"{self.http_url}/set_group_leave", {
            "group_id": group_id,
            "is_dismiss": is_dismiss
        })
        if result["status"] == "ok":
            return True
        return False

    def setGroupSpecialTitle(self,
                             group_id: int,
                             user_id: int,
                             special_title: str = "",
                             duration: int = -1) -> bool:
        result = self._sent_post(f"{self.http_url}/set_group_special_title", {
            "group_id": group_id,
            "user_id": user_id,
            "special_title": special_title,
            "duration": duration
        })
        if result["status"] == "ok":
            return True
        return False

    def setFriendRequest(self,
                         flag: str,
                         approve: bool = True,
                         remark: str = "") -> bool:
        result = self._sent_post(f"{self.http_url}/set_friend_add_request", {
            "flag": flag,
            "approve": approve,
            "remark": remark
        })
        if result["status"] == "ok":
            return True
        return False

    def setGroupRequest(self,
                        flag: str,
                        sub_type: str,
                        approve: bool = True,
                        reason: str = "") -> bool:
        if sub_type not in ["add", "invite"]:
            return False
        result = self._sent_post(f"{self.http_url}/set_group_add_request", {
            "flag": flag,
            "sub_type": sub_type,
            "approve": approve,
            "reason": reason
        })
        if result["status"] == "ok":
            return True
        return False

    def getLoginInfo(self) -> T.Union[Bot, bool]:
        result = self._sent_post(f"{self.http_url}/get_login_info")
        if result["status"] == "ok":
            return Bot.model_validate(result["data"])
        return False

    def getQiDianAccountInfo(self) -> T.Union[QiDianAccount, bool]:
        result = self._sent_post(
            f"{self.http_url}/qidian_get_account_info")
        if result["status"] == "ok":
            return QiDianAccount.model_validate(result["data"])
        return False

    def getStrangerInfo(self,
                        user_id: int,
                        no_cache: bool = False) -> T.Union[Stranger, bool]:
        result = self._sent_post(f"{self.http_url}/get_stranger_info", {
            "user_id": user_id,
            "no_cache": no_cache
        })
        if result["status"] == "ok":
            return Stranger.model_validate(result["data"])
        return False

    def getFriendList(self) -> T.Union[List[Friend], bool]:
        result = self._sent_post(f"{self.http_url}/get_friend_list")
        if result["status"] == "ok":
            return [Friend.model_validate(friend_info) for friend_info in result["data"]]
        return False

    def deleteFriend(self,
                     friend_id: int) -> bool:
        result = self._sent_post(f"{self.http_url}/delete_friend", {
            "friend_id": friend_id
        })
        if result["status"] == "ok":
            return True
        return False

    def getUnidirectionalFriendList(self) -> T.Union[List[Friend], bool]:
        result = self._sent_post(
            f"{self.http_url}/get_unidirectional_friend_list")
        if result["status"] == "ok":
            return [Friend.model_validate(friend_info) for friend_info in result["data"]]
        return False

    def deleteUnidirectionalFriend(self,
                                   user_id: int) -> bool:
        result = self._sent_post(f"{self.http_url}/delete_unidirectional_friend", {
            "user_id": user_id
        })
        if result["status"] == "ok":
            return True
        return False

    def getGroupInfo(self,
                     group_id: int,
                     no_cache: bool = False) -> T.Union[Group, bool]:
        result = self._sent_post(f"{self.http_url}/get_group_info", {
            "group_id": group_id,
            "no_cache": no_cache
        })
        if result["status"] == "ok":
            return Group.model_validate(result["data"])
        return False

    def getGroupList(self) -> T.Union[List[Group], bool]:
        result = self._sent_post(f"{self.http_url}/get_group_list")
        if result["status"] == "ok":
            return [Group.model_validate(group_info) for group_info in result["data"]]
        return False

    def getGroupMemberInfo(self,
                           group_id: int,
                           user_id: int,
                           no_cache: bool = False) -> T.Union[Member, bool]:
        result = self._sent_post(f"{self.http_url}/get_group_member_info", {
            "group_id": group_id,
            "user_id": user_id,
            "no_cache": no_cache
        })
        if result["status"] == "ok":
            return Member.model_validate(result["data"])
        return False

    def getGroupMemberList(self,
                           group_id: int) -> T.Union[List[Member], bool]:
        result = self._sent_post(f"{self.http_url}/get_group_member_list", {
            "group_id": group_id
        })
        if result["status"] == "ok":
            return [Member.model_validate(member_info) for member_info in result["data"]]
        return False

    def getGroupHonorInfo(self,
                          group_id: int,
                          type: str) -> T.Union[Honor, bool]:
        result = self._sent_post(f"{self.http_url}/get_group_honor_info", {
            "group_id": group_id,
            "type": type
        })
        if result["status"] == "ok":
            return Honor.model_validate(result["data"])
        return False

    def canSendImage(self) -> bool:
        result = self._sent_post(f"{self.http_url}/can_send_image")
        if result["status"] == "ok":
            if result["data"]["yes"]:
                return True
        return False

    def canSendRecord(self) -> bool:
        result = self._sent_post(f"{self.http_url}/can_send_record")
        if result["status"] == "ok":
            if result["data"]["yes"]:
                return True
        return False

    def getVersionInfo(self) -> T.Union[AppVersion, bool]:
        result = self._sent_post(f"{self.http_url}/get_version_info")
        if result["status"] == "ok":
            return AppVersion.model_validate(result["data"])
        return False

    def restartAPI(self, delay: int = 0) -> bool:
        result = self._sent_post(f"{self.http_url}/set_restart", {
            "delay": delay
        })
        if result["status"] == "ok":
            return True
        return False

    def setGroupPortrait(self,
                         group_id: int,
                         file: str,
                         cache: int) -> bool:
        result = self._sent_post(f"{self.http_url}/set_restart", {
            "group_id": group_id,
            "file": file,
            "cache": cache
        })
        if result["status"] == "ok":
            return True
        return False

    def ocrImage(self,
                 image: str) -> T.Union[OCR, bool]:
        result = self._sent_post(f"{self.http_url}/ocr_image", {
            "image": image
        })
        if result["status"] == "ok":
            return OCR.model_validate(result["data"])
        return False

    def getGroupSystemMessage(self) -> T.Union[GroupSystemMessage, bool]:
        result = self._sent_post(f"{self.http_url}/get_group_system_msg")
        if result["status"] == "ok":
            return GroupSystemMessage.model_validate(result["data"])
        return False

    def uploadGroupFile(self, group_id: int) -> T.Union[GroupFileSystem, bool]:
        result = self._sent_post(f"{self.http_url}/get_group_file_system_info", {
            "group_id": group_id
        })
        if result["status"] == "ok":
            return GroupFileSystem.model_validate(result["data"])
        return False

    def getGroupRootFiles(self, group_id: int) -> T.Union[GroupFileTree, bool]:
        result = self._sent_post(f"{self.http_url}/get_group_root_files", {
            "group_id": group_id
        })
        if result["status"] == "ok":
            return GroupFileTree.model_validate(result["data"])
        return False

    def getGroupFilesByFolder(self,
                              group_id: int,
                              folder_id: str) -> T.Union[GroupFileTree, bool]:
        result = self._sent_post(f"{self.http_url}/get_group_root_files", {
            "group_id": group_id,
            "folder_id": folder_id
        })
        if result["status"] == "ok":
            return GroupFileTree.model_validate(result["data"])
        return False

    def getGroupFileURL(self,
                        group_id: int,
                        file_id: str,
                        busid: int) -> T.Union[str, bool]:
        result = self._sent_post(f"{self.http_url}/get_group_file_url", {
            "group_id": group_id,
            "file_id": file_id,
            "busid": busid
        })
        if result["status"] == "ok":
            return result["data"]["url"]
        return False

    def getStatus(self) -> T.Union[AppStatus, bool]:
        result = self._sent_post(f"{self.http_url}/get_status")
        if result["status"] == "ok":
            return AppStatus.model_validate(result["data"])
        return False

    def getGroupAtAllRemain(self, group_id: int) -> T.Union[AtAllRemain, bool]:
        result = self._sent_post(f"{self.http_url}/get_group_at_all_remain", {
            "group_id": group_id
        })
        if result["status"] == "ok":
            return AtAllRemain.model_validate(result["data"])
        return False

    def getVipInfo(self, user_id: int) -> T.Union[VipInfo, bool]:
        result = self._sent_post(f"{self.http_url}/_get_vip_info", {
            "user_id": user_id
        })
        if result["status"] == "ok":
            return VipInfo.model_validate(result["data"])
        return False

    def sendGroupNotice(self, group_id: int, content: str):
        result = self._sent_post(f"{self.http_url}/_send_group_notice", {
            "group_id": group_id,
            "content": content
        })
        if result["status"] == "ok":
            return True
        return False

    def reloadEventFilter(self, file: str):
        result = self._sent_post(f"{self.http_url}/reload_event_filter", {
            "file": file
        })
        if result["status"] == "ok":
            return True
        return False

    def downloadFile(self, url: str, headers: str, thread_count=1):
        result = self._sent_post(f"{self.http_url}/download_file", {
            "url": url,
            "headers": headers,
            "thread_count": thread_count
        })
        if result["status"] == "ok":
            return True
        return False

    def getOnlineClients(self, no_cashe: bool) -> T.Union[List[Device], bool]:
        result = self._sent_post(f"{self.http_url}/get_online_clients", {
            "no_cache": no_cashe
        })
        if result["status"] == "ok":
            return [Device.model_validate(device) for device in result["data"]["clients"]]
        return False

    def getGroupMessageHistory(self, group_id: int, message_seq: Optional[int] = None) -> T.Union[List[Message], bool]:
        result = self._sent_post(f"{self.http_url}/get_group_msg_history", {
            "message_seq": message_seq,
            "group_id": group_id
        })
        if result["status"] == "ok":
            print(result)
            return [Message.model_validate(message) for message in result["data"]["messages"]]
        return False

    def setEssenceMessage(self, message_id: int) -> bool:
        result = self._sent_post(f"{self.http_url}/set_essence_msg", {
            "message_id": message_id
        })  # 草,为什么只有手机看得到
        if result["status"] == "ok":
            return True
        return False

    def deleteEssenceMessage(self, message_id: int) -> bool:
        result = self._sent_post(f"{self.http_url}/delete_essence_msg", {
            "message_id": message_id
        })  # 这个我没测试过
        if result["status"] == "ok":
            return True
        return False

    def getEssenceMessageList(self, group_id: int) -> T.Union[EssenceMessage, bool]:
        result = self._sent_post(f"{self.http_url}/get_essence_msg_list", {
            "group_id": group_id
        })
        if result["status"] == "ok":
            return EssenceMessage.model_validate(result["data"])
        return False

    def checkURLSafety(self, url: str) -> int:
        result = self._sent_post(f"{self.http_url}/check_url_safely", {
            "url": url
        })
        if result["status"] == "ok":
            return result["level"]
        return False

    def getModelShow(self, model: str) -> T.Union[List[ModelShow], bool]:
        result = self._sent_post(f"{self.http_url}/_get_model_show", {
            "model": model
        })
        if result["status"] == "ok":
            return [ModelShow.model_validate(_model) for _model in result["data"]["variants"]]
        return False

    def setModelShow(self, model: str, model_show: str) -> bool:
        result = self._sent_post(f"{self.http_url}/_set_model_show", {
            "model": model,
            "model_show": model_show
        })
        if result["status"] == "ok":
            return True
        return False

    def getGuildServiceProfile(self) -> T.Union[BotGuild, bool]:
        '''
        获取频道系统内BOT的资料
        '''
        result = self._sent_post(
            f"{self.http_url}/get_guild_service_profile")
        if result["status"] == "ok":
            return BotGuild.model_validate(result["data"])
        return False

    def getGuildList(self) -> T.Union[list, bool]:
        '''
        获取频道列表
        '''
        result = self._sent_post(f"{self.http_url}/get_guild_list")
        if result["status"] == "ok":
            return [Guild.model_validate(_guild) for _guild in result["data"]]
        return False

    def getGuildMetaByGuest(self, guild_id: int) -> T.Union[Guild, bool]:
        '''
        通过访客获取频道元数据
        '''
        result = self._sent_post(f"{self.http_url}/get_guild_meta_by_guest", {
            "guild_id": guild_id
        })
        if result["status"] == "ok":
            return Guild.model_validate(result["data"])
        return False

    def getGuildChannelList(self, guild_id: int, no_cache: bool = False) -> T.Union[list, bool]:
        '''
        获取子频道列表
        '''
        result = self._sent_post(f"{self.http_url}/get_guild_channel_list", {
            "guild_id": guild_id,
            "no_cache": no_cache
        })
        if result["status"] == "ok":
            return [Channel.model_validate(_channel) for _channel in result["data"]]
        return False

    def getGuildMembers(self, guild_id: int) -> T.Union[GuildMembers, bool]:
        '''
        获取频道成员列表
        '''
        result = self._sent_post(f"{self.http_url}/get_guild_members", {
            "guild_id": guild_id
        })
        if result["status"] == "ok":
            return GuildMembers.model_validate(result["data"])
        return False

    def sendGuildChannelMessage(self, guild_id: int, channel_id: int, message: T.Union[str, list]) -> T.Union[BotMessage, bool]:
        '''
        发送信息到子频道
        '''
        if isinstance(message, list):
            _message = ""
            for chain in message:
                _message += chain.toString()
            message = _message
        result = self._sent_post(f"{self.http_url}/send_guild_channel_msg", {
            "guild_id": guild_id,
            "channel_id": channel_id,
            "message": message
        })
        if result["status"] == "ok":
            return BotMessage.model_validate(result["data"])
        return False

    def getGuildRoles(self, guild_id: int) -> T.Union[Role, bool]:
        '''
        获取频道身份组列表
        '''
        result = self._sent_post(f"{self.http_url}/get_guild_roles", {
            "guild_id": guild_id
        })
        if result["status"] == "ok":
            return [Role.model_validate(_role) for _role in result["data"]]
        return False

    def createGuildRole(self, guild_id: int, name: str, color: int, independent: bool, initial_users: T.List[int] = []) -> T.Union[Role, bool]:
        '''
        创建频道身份组
        '''
        result = self._sent_post(f"{self.http_url}/create_guild_role", {
            "guild_id": guild_id,
            "name": name,
            "color": color,
            "independent": independent,
            "initial_users": initial_users
        })
        if result["status"] == "ok":
            return Role.model_validate(result["data"])
        return False

    def deleteGuildRole(self, guild_id: int, role_id: int) -> bool:
        '''
        删除频道身份组
        '''
        result = self._sent_post(f"{self.http_url}/delete_guild_role", {
            "guild_id": guild_id,
            "role_id": role_id
        })
        if result["status"] == "ok":
            return True
        return False

    def setGuildMemberRole(self, guild_id: int, role_id: int, users: T.List[int]) -> bool:
        '''
        设置用户在频道中的身份组
        '''
        result = self._sent_post(f"{self.http_url}/set_guild_member_role", {
            "guild_id": guild_id,
            "role_id": role_id,
            "users": users
        })
        if result["status"] == "ok":
            return True
        return False

    def editGuildRole(self, guild_id: int, role_id: int, name: str, color: int, independent: bool) -> bool:
        '''
        设置用户在频道中的身份组
        '''
        result = self._sent_post(f"{self.http_url}/update_guild_role", {
            "guild_id": guild_id,
            "role_id": role_id,
            "name": name,
            "color": color,
            "independent": independent  # TODO gocq 中参数名写错了, 待后续确认
        })
        if result["status"] == "ok":
            return True
        return False

    def getTopicChannelFeeds(self, guild_id: int, channel_id: int) -> T.Union[T.List[TopicChannelFeed], bool]:
        '''
        获取论坛子频道帖子列表
        '''
        result = self._sent_post(f"{self.http_url}/get_topic_channel_feeds", {
            "guild_id": guild_id,
            "channel_id": channel_id
        })
        if result["status"] == "ok":
            return [TopicChannelFeed.model_validate(_feed) for _feed in result["data"]]
        return False
