

import calendar
import json
import msvcrt
import random
import re
import time
from datetime import datetime

import Events
from Models.Plugins import *

from ..gocqOnQQ.CQHTTP_Protocol.CQHTTP_Protocol import CQHTTP_Protocol
from ..cmdTimeReminder import get, get_words


class RunningFlag:
    def __init__(self) -> None:
        self.flag = False


@register(
    description="定时提醒[a, alarm]",
    version="1.0.0",
    author="For_Lin0601",
    priority=204,
    # enabled=False  # TODO 这个文件搜一下TODO, 此文件复用性低, 需注释掉一些才可被复用。故默认关闭
)
class TimeReminderCommand(Plugin):

    @on(PluginsLoadingFinished)
    @on(PluginsReloadFinished)
    def start_timed_reminder(self, event: EventContext, **kwargs):
        self.running_flag = RunningFlag()
        self.running_flag.flag = True
        self.emit(SubmitSysTask__, fn=self.timed_reminder_handle)

    def on_reload(self):
        self.running_flag.flag = False

    def on_stop(self):
        self.running_flag.flag = False

    @on(CmdCmdHelp)
    def help(self, event: EventContext, **kwargs):
        event.return_value["alarm"] = {
            "is_admin": False,
            "alias": ["a"],
            "summary": "定时提醒",
            "usage": (
                "!alarm\n"
                " - 定时提醒\n"
                "!alarm ls\n"
                " - 查看所有定时提醒\n"
                "!alarm all\n"
                " - [管理员]查看所有定时提醒\n"
                "!alarm d [编号]\n"
                " - 删除指定定时提醒\n"
                "!alarm set [编号] [城市]\n"
                " - 设置每日短句"
            ),
            "description": "详情请输入`!alarm`查看, 在此不赘述, 可用作闹钟, 但还请注意QQ存在意外掉线的问题, 所以请勿过于依赖此功能"
        }

    @on(GetQQPersonCommand)
    def add_time_reminder(self, event: EventContext, **kwargs):
        message: str = kwargs["message"].strip()
        pattern_alarm = r'^a[^a-zA-Z]+'
        if not (re.search(pattern_alarm, message) or message == "a" or message.startswith("alarm")):
            return
        event.prevent_postorder()
        if message.startswith("alarm"):
            message = message[5:].strip()
        else:
            message = message[1:].strip()
        params = message.split()
        cqhttp: CQHTTP_Protocol = self.emit(Events.GetCQHTTP__)
        sender_id = kwargs["sender_id"]
        config = self.emit(Events.GetConfig__)
        if len(params) == 0:
            reply = "[bot] 欢迎使用定时提醒~"
            reply += "\n-> 标准格式:\n时间 [重复间隔 重复次数]  #内容"
            reply += "\n-------------"
            reply += "\n!a 2000/1/1 7:00:00  #早安"
            reply += "\n!a 2000/1/1 7:00:00 每天 5次  #早安"
            reply += "\n-------------"
            reply += "\n- 间隔单位: 年月日时分秒"
            reply += "\n- 次数单位: ？次/无限"
            reply += "\n- 允许出现空缺, 会一定程度地自动填充"
            reply += "\n- 井号 (#) 为时间标识, 仅会展示井号 (#) 之后的信息, 可忽略"
            reply += "\n- 因为本定时提醒基于QQ机器人, 所以请勿过于依赖此功能。不排除机器人停机等意外情况！！！"
            reply += "\n\n-> 由于标准格式过于复杂, 所以支持 [自然语言识别]"
            reply += "\n-------------"
            reply += "\n!a 明早八点叫醒我xxx"
            reply += "\n!a 下个月六号提醒我xxx"
            reply += "\n-------------"
            reply += "\n- 请注意 [自然语言识别] 能力有限！"
            reply += "\n\n-> 子命令:"
            reply += "\n[!a ls]"
            reply += "\n- 查看当前所有定时提醒"
            reply += "\n[!a all]"
            reply += "\n- 管理员命令, 查看当前所有定时提醒"
            reply += "\n[!a d 1]"
            reply += "\n- 删除编号为 [1] 的定时提醒"
            reply += "\n[!a set 1 杭州]"
            reply += "\n- 为编号为 [1] 的定时提醒添加城市天气查询"
            reply += "\n- 城市名应为市级, 支持模糊查找"
            reply += "\n- 可用 !a 明早八点#[!杭州]早安~ 快速设置天气查询"
            cqhttp.sendPersonMessage(sender_id, reply)
            return

        pattern_delete = r'^d\d*$'
        match_delete = re.search(pattern_delete, ''.join(params))
        pattern_set = r'^set\d+.+$'
        match_set = re.search(pattern_set, ''.join(params))
        if params[0] == "ls" or params[0] == "all" or match_delete or match_set:

            if params[0] == "all" and sender_id not in config.admin_list:
                cqhttp.sendPersonMessage(sender_id, "[bot] 权限不足")
                return
            elif sender_id in config.admin_list and (params[0] == "all" or match_delete or match_set):
                params_admin = True
            else:
                params_admin = False

            if match_delete:
                params_id = ''.join(params)[1:]
            elif match_set:
                city_str = ''.join(params)[3:]
                params_id = ''
                while city_str[0].isdigit():
                    params_id += city_str[0]
                    city_str = city_str[1:]
            else:
                params_id = ''

            reply = "[bot] 当前所有定时提醒:"
            current_file_path = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(current_file_path, "waiting_events.txt")
            with open(file_path, "r+", encoding="utf-8") as file:
                file_descriptor = file.fileno()
                msvcrt.locking(file_descriptor, msvcrt.LK_LOCK, 1)

                # 读取文件内容
                lines = file.readlines()
                for index, line in enumerate(lines):
                    split_data = line.split()
                    qq_number = split_data[11]  # QQ号
                    if not (int(qq_number) == sender_id or params_admin):
                        continue

                    event_id = split_data[0]  # 编号
                    event_date_describe = split_data[1]  # 日期
                    event_time = split_data[2]  # 时间
                    time_delta = [int(split_data[i]) for i in range(3, 9)]  # 重复步频
                    if time_delta[1] != 0:
                        split_date = event_date_describe.split('/')
                        event_date1 = min(int(split_date[2]), calendar.monthrange(int(split_date[0]), int(split_date[1]))[1])
                        event_date = "{}/{}/{}".format(split_date[0], split_date[1], event_date1)
                    else:
                        event_date = event_date_describe
                    repeat_count = int(split_data[9])  # 重复次数
                    qq_name = split_data[10]  # QQ名字
                    message = ' '.join(split_data[12:])  # 定时提醒内容

                    if repeat_count > 0:
                        reply_continue = "\n重复: 剩余 [{}] 次~".format(repeat_count + 1)
                    elif repeat_count < 0:
                        reply_continue = "\n重复: 进行中~"
                    elif not all(delta == 0 for delta in time_delta):
                        reply_continue = "\n重复: 最后 [1] 次~"
                    else:
                        reply_continue = "\n重复: 无"

                    if repeat_count != 0:
                        year_month_day_time = ["年", "月", "天", "小时", "分钟", "秒"]
                        reply_continue += "\n间隔: 每 ["
                        for i in range(6):
                            if time_delta[i] != 0:
                                reply_continue += "{}{}".format(time_delta[i], year_month_day_time[i])
                                break
                        reply_continue += "] 一次"

                    reply_line = "\n\n编号: [{}]{}\n昵称: [{}]\nQQ号: [{}]\n时间: [{}]\n信息: [{}]".format(
                        event_id, reply_continue, qq_name, qq_number, event_date + ' ' + event_time,
                        message[:min(40, len(message))] + ("   ..." if len(message) > 40 else ''))

                    if event_id == params_id:
                        # 删除定时提醒
                        if match_delete:
                            lines.remove(line)
                            file.seek(0)
                            file.writelines(lines)
                            file.truncate()
                            cqhttp.sendPersonMessage(sender_id, "[bot] 已删除编号为 [{}] 的定时提醒{}".format(event_id, reply_line))
                            return

                        # 设置天气预报
                        elif match_set:
                            match_message_startwith = re.match(r'^\[!(.+?)\]', message)
                            if match_message_startwith:
                                city = match_message_startwith.group(1)
                                message = message.replace(f"[!{city}]", f"[!{city_str}]")
                            else:
                                message = f"[!{city_str}]{message}"
                            lines[index] = ' '.join(split_data[:12]) + ' ' + message
                            lines[index] = lines[index].strip()
                            if not lines[index].endswith('\n'):
                                lines[index] += '\n'
                            file.seek(0)
                            file.writelines(lines)
                            file.truncate()
                            cqhttp.sendPersonMessage(sender_id, "[bot] 成功设置天气预报~{}\n城市更新: [{}]".format(reply_line, city_str))
                            return

                    # 查看当前权限内所有定时提醒
                    reply += reply_line

                else:
                    if match_delete or match_set:
                        cqhttp.sendPersonMessage(sender_id, "[bot] 未找到编号为 [{}] 的定时提醒".format(params_id))
                        return

            if reply == "[bot] 当前所有定时提醒:":
                reply = "\n[bot] 未查询到定时提醒！\n!a 查看帮助"
            else:
                reply = self.emit(ForwardMessage__, message=reply)
                cqhttp.sendPersonForwardMessage(sender_id, reply)
                return
            cqhttp.sendPersonMessage(sender_id, reply)
            return

        elif ''.join(params).startswith("set"):
            cqhttp.sendPersonMessage(sender_id, "[bot]err: set命令格式错误!\n请用以下命令重设城市名:\n-------------\n!a set <闹钟编号> <城市名>\n-------------\n其中 <闹钟编号> 可用命令: !a ls 查询")
            return

        else:
            try:
                text = ' '.join(params)
                text = text.replace('【', '[').replace('】', ']').replace('！', '!').replace('：', ':').replace('\\', '/')
                if "#" in text:
                    text_time, text_message = text.split("#", 1)
                else:
                    text_time = text_message = text
                match_text_message_startwith = re.match(r'^\[!(.+?)\]', text_message)
                if match_text_message_startwith:
                    city = match_text_message_startwith.group(1)
                    if text_message.replace(f"[!{city}]", "") == '' and text_time == text:
                        text_time += '两秒后'
                        text_message += f'{city}天气查询~'
                event_date, event_time, frequency_dict, count_dict = get_words.get_words(text_time)
                qq_name = cqhttp.getStrangerInfo(sender_id).nickname
            except Exception as e:
                cqhttp.sendPersonMessage(sender_id, "[bot]err: 未知错误！\n请用 !a 查看帮助\n或用 !s <对话内容> 向管理员寻求帮助\n{}".format(e))
                return

            pattern = r"(\d+):(\d+):(\d+)"
            match = re.search(pattern, text_message)
            if match:
                text_message = text_message.replace(match.group(), '')
            pattern = r"(\d+)/(\d+)/(\d+)"
            match = re.search(pattern, text_message)
            if match:
                text_message = text_message.replace(match.group(), '')
            text_message = text_message.strip()
            if text_message == '':
                text_message = "定时提醒~"

            reply = get_words.user_event_input(qq_name=qq_name, qq_number=str(sender_id),
               event_date_describe=event_date, event_time=event_time, time_delta=frequency_dict, repeat_count=count_dict,
               message=text_message)

            cqhttp.sendPersonMessage(sender_id, reply)
            return

    @on(GetQQGroupCommand)
    def group_send(self, event: EventContext, **kwargs):
        message: str = kwargs["message"].strip()
        pattern_alarm = r'^a[^a-zA-Z]+'
        if not (re.search(pattern_alarm, message) or message == "a" or message.startswith("alarm")):
            return
        event.prevent_postorder()
        cqhttp: CQHTTP_Protocol = self.emit(Events.GetCQHTTP__)
        group_id = kwargs["group_id"]
        cqhttp.sendGroupMessage(group_id, "[bot] 群聊暂不支持此命令")

    @on(GetWXCommand)
    def wx_send(self, event: EventContext, **kwargs):
        message: str = kwargs["command"].strip()
        pattern_alarm = r'^a[^a-zA-Z]+'
        if not (re.search(pattern_alarm, message) or message == "a" or message.startswith("alarm")):
            return
        event.prevent_postorder()
        sender = kwargs["roomid"] if kwargs["roomid"] else kwargs["sender"]
        self.emit(Events.GetWCF__).send_text("[bot] 微信暂不支持此命令", sender)

    def timed_reminder_handle(self):
        """定时提醒"""
        current_file_path = os.path.dirname(os.path.abspath(__file__))
        target_file_path = os.path.join(current_file_path, "waiting_events.txt")
        sleep = False
        match_message_startwith = False
        innermost, copywriting, news, get_list = self.get_gets()
        current_time = time.localtime()
        check_internet_status_perday = False
        previous_day = current_time.tm_mday
        previous_hour = current_time.tm_hour
        previous_minute = current_time.tm_min

        while True:
            if sleep:
                time.sleep(1)
            else:
                time.sleep(0.2)
                sleep = True

            if self.running_flag.flag is False:
                break

            try:
                # 三小时刷新一次每日推荐
                current_time = time.localtime()
                if current_time.tm_mday != previous_day or (current_time.tm_hour - previous_hour) >= 3:
                    sleep = True
                    previous_day = current_time.tm_mday
                    previous_hour = current_time.tm_hour
                    innermost, copywriting, news, get_list = self.get_gets()

            except Exception as e:
                sleep = True
                time.sleep(0.2)
                cqhttp: CQHTTP_Protocol = self.emit(GetCQHTTP__)
                cqhttp.NotifyAdmin(f"err: 定时提醒 [每日推荐更新模块] 未知错误!!!\n[{e}]")

            try:
                with open(target_file_path, "r+", encoding="utf-8") as file:
                    file_descriptor = file.fileno()
                    msvcrt.locking(file_descriptor, msvcrt.LK_LOCK, 1)

                    # 读取文件内容
                    lines = file.readlines()
                    if lines:
                        first_line = lines[0].strip()
                        split_data = first_line.split()

                        # 判断是否到达时间
                        event_date_describe = split_data[1]  # 日期
                        event_time = split_data[2]  # 时间
                        time_delta = [int(split_data[i]) for i in range(3, 9)]  # 重复步频
                        if time_delta[1] != 0:
                            split_date = event_date_describe.split("/")
                            event_date1 = min(int(split_date[2]), calendar.monthrange(int(split_date[0]), int(split_date[1]))[1])
                            event_date = "{}/{}/{}".format(split_date[0], split_date[1], event_date1)
                        else:
                            event_date = event_date_describe
                        date_time = time.strptime(event_date + ' ' + event_time, "%Y/%m/%d %H:%M:%S")

                        if current_time >= date_time:
                            event_id = split_data[0]  # 编号
                            repeat_count = int(split_data[9])  # 重复次数
                            qq_name = split_data[10]  # QQ名字
                            qq_number = int(split_data[11])  # QQ号
                            message = ' '.join(split_data[12:])  # 定时提醒内容

                            sleep = False
                            time_diff = (time.mktime(current_time) - time.mktime(date_time)) // 60

                            if repeat_count > 0:
                                reply_continue = "\n重复: 剩余 [{}] 次~".format(repeat_count + 1)
                                reply_continue_default = "\n重复: 获取剩余次数失败!"
                            elif repeat_count < 0:
                                reply_continue = "\n重复: 进行中~"
                                reply_continue_default = "\n重复: 重复进行中~"
                            elif not all(delta == 0 for delta in time_delta):
                                reply_continue = "\n重复: 最后 [1] 次~"
                                reply_continue_default = "\n重复: 最后 [1] 次~"
                            else:
                                reply_continue = "\n重复: 无"
                                reply_continue_default = "\n重复: 无"

                            if repeat_count != 0:
                                year_month_day_time = ["年", "月", "天", "小时", "分钟", "秒"]
                                reply_continue_or_default = "\n间隔: ["
                                for i in range(6):
                                    if time_delta[i] != 0:
                                        reply_continue_or_default += "{}{}".format(time_delta[i], year_month_day_time[i])
                                        break
                                reply_continue_or_default += "] 一次"
                                reply_continue += reply_continue_or_default
                                reply_continue_default += reply_continue_or_default

                            match_message_startwith = re.match(r'^\[!(.+?)\]', message)
                            if match_message_startwith:
                                city = match_message_startwith.group(1)
                                message_reply = message.replace(f"[!{city}]", "")
                            else:
                                message_reply = message

                            # 超时一分钟以上
                            if time_diff >= 1:
                                match_message_startwith = False
                                if repeat_count == -2:
                                    repeat_count = -1
                                else:
                                    cqhttp = self.emit(GetCQHTTP__)
                                    try:
                                        cqhttp.sendPersonMessage(qq_number, "[bot]err: 未知原因!检测到您的定时提醒已过期!\n编号: [{}]{}\n昵称: [{}]\n时间: [{}]\n信息: [{}]".format(
                                            event_id, reply_continue_default, qq_name, event_date + ' ' + event_time, message_reply))
                                    except:
                                        reply_continue_default += "\n[bot]err: 消息提醒没有成功发出!"
                                    cqhttp.NotifyAdmin("err: 未知原因!检测到定时提醒已过期!\n编号: [{}]{}\n昵称: [{}]\nQQ号: [{}]\n时间: [{}]\n信息: [{}]".format(
                                        event_id, reply_continue_default, qq_name, qq_number, event_date + ' ' + event_time,
                                        message[:min(40, len(message))] + ("   ..." if len(message) > 40 else "")))

                            # 正常发送提醒
                            elif current_time >= date_time:
                                cqhttp = self.emit(GetCQHTTP__)
                                try:
                                    cqhttp.sendPersonMessage(qq_number, "[bot] 您的定时提醒已送达~\n编号: [{}]{}\n昵称: [{}]\n时间: [{}]\n信息: [{}]".format(
                                        event_id, reply_continue, qq_name, event_date + ' ' + event_time, message_reply))
                                except:
                                    repeat_count = 0
                                    cqhttp.NotifyAdmin("err: 检测到消息提醒没有成功发出!!!\n编号: [{}]{}\n昵称: [{}]\nQQ号: [{}]\n时间: [{}]\n信息: [{}]".format(
                                        event_id, reply_continue_default, qq_name, qq_number, event_date + ' ' + event_time,
                                        message[:min(40, len(message))] + ("   ..." if len(message) > 40 else "")))

                            # 删除此定时提醒
                            if repeat_count == 0:
                                file.seek(0)
                                file.write(''.join(lines[1:]))
                                file.truncate()

                            # 重新设置此定时提醒并插入文件合适位置
                            else:
                                pd_continue = False  # 过期的申请是否删除
                                new_datetime = get.add_datetime(date_time, *time_delta)
                                if repeat_count > 0:
                                    repeat_count -= 1
                                # 循环直到超过当前时间
                                while (time.mktime(current_time) - time.mktime(new_datetime)) > 1:
                                    new_datetime = get.add_datetime(new_datetime, *time_delta)
                                    if repeat_count > 0:
                                        repeat_count -= 1
                                    elif repeat_count == 0:
                                        file.seek(0)
                                        file.write(''.join(lines[1:]))
                                        file.truncate()
                                        pd_continue = True
                                        break
                                if not pd_continue:
                                    try:
                                        lines = lines[1:]
                                    except:
                                        pass
                                    insert_data = datetime.strptime(datetime(*new_datetime[:6]).strftime("%Y-%m-%d %H:%M:%S"), "%Y-%m-%d %H:%M:%S")

                                    # 如果步频为 '月', 则 insert_date 记录回之前的 '日'
                                    if time_delta[1] != 0:
                                        insert_date1 = insert_data.strftime('%Y/%m/%d %H:%M:%S')
                                        insert_date2 = insert_date1.split(' ')
                                        insert_date3 = insert_date2[0].split('/')
                                        insert_date4 = "{}/{}/{}".format(insert_date3[0], insert_date3[1], split_date[2])
                                        insert_date = insert_date4 + ' ' + insert_date2[1]
                                    else:
                                        insert_date = insert_data.strftime('%Y/%m/%d %H:%M:%S')
                                    reply = f"{event_id} {insert_date} {' '.join(str(x) for x in time_delta)} {repeat_count} {qq_name} {qq_number} {message}\n"

                                    for i, line in enumerate(lines):
                                        line_data_describe = line.split()[1:3]
                                        line_data1 = line_data_describe[0].split("/")
                                        line_data2 = min(int(line_data1[2]), calendar.monthrange(int(line_data1[0]), int(line_data1[1]))[1])
                                        line_data = "{}/{}/{} {}".format(line_data1[0], line_data1[1], line_data2, line_data_describe[1])
                                        line_datetime = datetime.strptime(line_data, "%Y/%m/%d %H:%M:%S")
                                        if insert_data < line_datetime:
                                            lines.insert(i, reply)
                                            break
                                    else:
                                        lines.append(reply)
                                    file.seek(0)
                                    file.writelines(lines)
                                    file.truncate()

                            # 每日推荐
                            try:
                                if time_diff <= 1 and match_message_startwith:
                                    cqhttp = self.emit(GetCQHTTP__)
                                    # 查询天气
                                    weather_reply = get.get_weather(city)
                                    if weather_reply == '-1':
                                        weather_reply = "[bot]err: ~~~天气查询~~~\n预留城市名称错误!\n请用以下命令重设城市名:\n!a set {} <城市名>".format(event_id)
                                    elif weather_reply == '-2':
                                        weather_reply = "[bot]err: ~~~天气查询~~~\n服务器请求错误!"
                                    cqhttp.sendPersonMessage(qq_number, weather_reply)

                                    # 查询每日推荐
                                    if qq_number in self.emit(GetConfig__).admin_list:
                                        message = get_list + innermost + copywriting + news
                                    else:
                                        message_innermost = [innermost[0] if 3 < current_time.tm_hour < 15 else innermost[1]]
                                        if len(copywriting) > 5:
                                            message_copywriting = random.sample(copywriting, random.randint(3, 5))
                                        elif copywriting:
                                            message_copywriting = copywriting
                                        else:
                                            message_copywriting = ["[bot]err: 今日语录抓取错误!"]
                                        if news:
                                            new_news = [random.choice(news)]
                                        else:
                                            new_news = ["[bot]err: 今日热点抓取错误!"]
                                        message = message_innermost + message_copywriting + new_news

                                    # 在这里添加翻译语言
                                    # if repeat_count == -3:
                                    #     message = [get.fanyi(item) for item in message]
                                    message = self.emit(ForwardMessage__, message=message)
                                    if not cqhttp.sendPersonForwardMessage(qq_number, message):
                                        cqhttp.sendPersonMessage(qq_number, "[bot]err: 每日推荐发送错误!")
                                        cqhttp.NotifyAdmin(f"err: [{qq_name}][{qq_number}]每日推荐发送错误!")

                            except Exception as e:
                                cqhttp.NotifyAdmin(f"err: [{qq_name}][{qq_number}]每日推荐发送错误!\n{e}")

            except Exception as e:
                sleep = True
                time.sleep(0.2)
                cqhttp = self.emit(GetCQHTTP__)
                cqhttp.NotifyAdmin(f"err: 定时提醒 [读取模块] 未知错误!!!\n[{e}]")

            # TODO 这一块是个人博客监控, 毫无复用性, 可注释掉
            # 其中用到的文件来自ssh远程修改, 故此处必然报错
            try:
                current_time = time.localtime()
                if previous_minute != current_time.tm_min:
                    previous_minute = current_time.tm_min
                    cqhttp = self.emit(GetCQHTTP__)
                    my_qq_number = self.emit(GetConfig__).my_qq_number
                    web_logs_reply = get.web_logs()
                    if web_logs_reply:
                        web_logs_reply_forward = self.emit(
                            Events.ForwardMessage__, message=web_logs_reply)
                        cqhttp.sendPersonForwardMessage(my_qq_number, web_logs_reply_forward)
            except Exception as e:
                cqhttp = self.emit(GetCQHTTP__)
                my_qq_number = self.emit(GetConfig__).my_qq_number
                cqhttp.sendPersonMessage(my_qq_number, f"[bot]err: [网站日志检测] 未知错误!!!\n[{e}]")

            # TODO 这一块是寝室电脑连接, 毫无复用性, 可注释掉
            # 其中用到的文件来自ssh远程修改, 故此处必然报错
            try:
                if (not check_internet_status_perday) and current_time.tm_hour == 7 and current_time.tm_min == 30:
                    check_internet_status_perday = True
                    cqhttp = self.emit(GetCQHTTP__)
                    my_qq_number = self.emit(GetConfig__).my_qq_number
                    get.check_internet_status(cqhttp, my_qq_number)
                elif check_internet_status_perday and current_time.tm_hour == 8:
                    check_internet_status_perday = False
            except Exception as e:
                cqhttp = self.emit(GetCQHTTP__)
                my_qq_number = self.emit(GetConfig__).my_qq_number
                cqhttp.sendPersonMessage(my_qq_number, f"[bot]err: [网络状态检测] 未知错误!\n[{e}]")

    def get_gets(self):
        """初始化每日推荐"""

        get_list = ['', '', '']

        # 获取每日心语
        innermost_list = ['早安心语', '晚安心语']
        innermost = get.get_day_night()
        innermost_texts = [text for index, text in enumerate(innermost_list) if innermost[index] == '-1']
        if innermost_texts:
            error_message = "[bot]err: 每日心语错误!!!"
            for innermost_text in innermost_texts:
                error_message += "\n[{}] 抓取错误".format(innermost_text)
            cqhttp: CQHTTP_Protocol = self.emit(GetCQHTTP__)
            cqhttp.NotifyAdmin(error_message)
            for i in range(len(innermost)):
                if innermost[i] == '-1':
                    innermost[i] = "[bot]err: [{}] 抓取错误".format(innermost_list[i])
            get_list[0] = "[bot] " + error_message

        # 获取每日语录
        copywriting_list = ['1.朋友圈文案', '2.失恋分手文案', '3.经典台词', '4.舔狗日记', '5.云音乐热评', '6.毒鸡汤', '7.彩虹屁', '8.ONE一个', '9.文化谚语', '10.谜语大全', '11.名人名言', '12.土味情话', '13.顺口溜', '14.神回复', '15.歇后语', '16.雷人笑话']
        copywriting = get.get_sentences_per_day()
        copywriting_texts = [text for index, text in enumerate(copywriting_list) if copywriting[index] == '-1']
        if copywriting_texts:
            error_message = "[bot]err: 每日语录错误!!!"
            for copywriting_text in copywriting_texts:
                error_message += "\n[{}] 抓取错误".format(copywriting_text)
            cqhttp: CQHTTP_Protocol = self.emit(GetCQHTTP__)
            cqhttp.NotifyAdmin(error_message)
            copywriting = [item for item in copywriting if item != '-1']
            get_list[1] = "[bot] " + error_message

        # 获取每日新闻
        news_list = ['1.天聚数行 AI新闻', '2.天聚数行 百度热搜', '3.天聚数行 每日简报']
        news = get.get_news()
        news_texts = [text for index, text in enumerate(news_list) if news[index] == '-1']
        if news_texts:
            error_message = "[bot]err: 每日新闻错误!!!"
            for news_text in news_texts:
                error_message += "\n[{}] 抓取错误".format(news_text)
            cqhttp: CQHTTP_Protocol = self.emit(GetCQHTTP__)
            cqhttp.NotifyAdmin(error_message)
            news = [item for item in news if item != '-1']
            get_list[2] = "[bot] " + error_message

        get_list = [text for text in get_list if text != '']

        innermost = [self.emit(BanWordProcess__, message=reply) for reply in innermost]
        copywriting = [self.emit(BanWordProcess__, message=reply) for reply in copywriting]
        news = [self.emit(BanWordProcess__, message=reply) for reply in news]

        # TODO 上传到网页, 此处也可注释掉
        daily_reminder_path = r"C:\wwwroot\backend\public\home\dailyReminder.json"
        if os.path.exists(daily_reminder_path):
            daily_reminder_content = {
                "updateTime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "innermost": innermost,
                "copywriting": copywriting,
                "news": news
            }
            with open(daily_reminder_path, 'w', encoding='utf-8') as f:
                f.write(json.dumps(daily_reminder_content, ensure_ascii=False))

        return innermost, copywriting, news, get_list
