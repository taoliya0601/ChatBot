import calendar
import hashlib
import json
import os
from pprint import pformat
import time
import requests
from datetime import datetime, timedelta

from ..gocqOnQQ.CQHTTP_Protocol.CQHTTP_Protocol import CQHTTP_Protocol
from Models.headers import get_random_ua
from functools import wraps

try:
    import config

    # 和风天气api
    he_feng_weather_key = config.he_feng_weather_key
    # 天聚数行api1
    tian_jv_shu_xing_api1 = config.tian_jv_shu_xing_api1
    # 天聚数行api2
    tian_jv_shu_xing_api2 = config.tian_jv_shu_xing_api2
    # 天聚数行api3
    tian_jv_shu_xing_api3 = config.tian_jv_shu_xing_api3
except:
    config = __import__(
        "plugins.cmdTimeReminder.config-template",
        globals(),
        locals(),
        fromlist=[
            "he_feng_weather_key",
            "tian_jv_shu_xing_api1",
            "tian_jv_shu_xing_api2",
            "tian_jv_shu_xing_api3",
        ],
    )
    # 和风天气api
    he_feng_weather_key = config.he_feng_weather_key
    # 天聚数行api1
    tian_jv_shu_xing_api1 = config.tian_jv_shu_xing_api1
    # 天聚数行api2
    tian_jv_shu_xing_api2 = config.tian_jv_shu_xing_api2
    # 天聚数行api3
    tian_jv_shu_xing_api3 = config.tian_jv_shu_xing_api3


def cache_with_time_limit(timeout=3600):
    """
    用于缓存函数的调用结果的装饰器\n
    缓存结果的过期时间默认为1小时
    """

    def decorator(func):
        cache = {}

        def _clear_expired_cache(now):
            expired_keys = []

            for key, value in cache.items():
                if now >= value["expire"]:
                    expired_keys.append(key)

            for key in expired_keys:
                del cache[key]

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = (func.__name__, args, frozenset(kwargs.items()))
            now = datetime.now()

            # 清理已过期的缓存
            _clear_expired_cache(now)

            # 检查缓存是否存在且未过期
            if key in cache and now < cache[key]["expire"]:
                return cache[key]["value"]

            result = func(*args, **kwargs)

            # 更新或添加缓存条目
            cache[key] = {"value": result, "expire": now + timedelta(seconds=timeout)}

            return result

        return wrapper

    if isinstance(timeout, int):
        return decorator
    elif callable(timeout):
        func = timeout
        timeout = 3600
        return decorator(func)
    else:
        raise TypeError("timeout must be int or callable")


@cache_with_time_limit
def get_weather(city: str) -> str:
    """获取该城市的天气预报, 若找不到该城市则返回 '-1', 服务器请求错误则返回 '-2'"""

    # 查找城市名
    city_url = f"https://geoapi.qweather.com/v2/city/lookup?location={city}&key={he_feng_weather_key}"
    try:
        city_result = requests.get(city_url, timeout=5).json()
    except:
        return "-2"
    try:
        city_data = city_result["location"][0]
    except:
        return "-1"

    # 获取对应天气预报
    weather_url = f"https://devapi.qweather.com/v7/weather/3d?location={city_data['id']}&key={he_feng_weather_key}"
    i = 0
    while i < 3:
        try:
            weather_result = requests.get(weather_url, timeout=5).json()
            break
        except:
            i += 1
    else:
        return "-2"

    forecast = weather_result["daily"][0]
    temp_max = int(forecast["tempMax"])
    precip = round(float(forecast["precip"]) * 12, 2)
    humidity = int(forecast["humidity"])
    pressure = int(forecast["pressure"])
    try:
        cloud = int(forecast["cloud"])
    except:
        cloud = -1
    vis = int(forecast["vis"])
    uv_index = int(forecast["uvIndex"])
    # 构建天气预报字符串
    content = (
        "[bot] ~~~天气查询~~~\n"
        f"地区: {city_data['country']}{city_data['adm1']}{city_data['adm2']}\n"
        f"日期: {forecast['fxDate']}\n"
        f"""天气: {forecast['textDay'] if forecast['textDay'] == forecast['textNight'] else f"{forecast['textDay']} 转 {forecast['textNight']}"}\n"""
        f"温度: {'寒冷' if temp_max <= 0 else '低温' if temp_max <= 10 else '温和' if temp_max <= 20 else '高温' if temp_max <= 30 else '炎热'} {forecast['tempMin']}~{temp_max}℃\n"
        f"""降水量: {'无降水' if precip <= 1 else f"{'小雨' if precip <= 5 else '中雨' if precip <= 15 else '大雨' if precip <= 30 else '暴雨' if precip <= 70 else '大暴雨' if precip <= 140 else '特大暴雨'} {forecast['precip']}mm/h"}\n"""
        f"风向-风速: {forecast['windDirDay']} {'快' if int(forecast['windSpeedDay']) > 10 else '慢'}\n"
        f"日出-日落: {forecast['sunrise']}-{forecast['sunset']}\n"
        f"月升-月落: {forecast['moonrise'] if forecast['moonrise'] != '' else '?'}-{forecast['moonset']} {forecast['moonPhase']}\n"
        f"湿度: {'特别干燥' if humidity <= 10 else '较干燥' if humidity <= 20 else '干燥' if humidity <= 30 else '舒适干燥' if humidity <= 40 else '轻微潮湿' if humidity <= 50 else '偏潮湿' if humidity <= 60 else '潮湿' if humidity <= 70 else '较潮湿' if humidity <= 80 else '特别潮湿'} {humidity}%\n"
        f"气压: {'低' if pressure < 1013 else '高'} {pressure}hPa\n"
        f"""云量: {'数据异常' if cloud == -1 else f"{'少云' if cloud <= 30 else '多云' if cloud <= 70 else '阴'} {cloud}%"}\n"""
        f"能见度: {'极差' if vis <= 1 else '差' if vis <= 10 else '较差' if vis <= 15 else '一般' if vis <= 20 else '较好' if vis <= 25 else '极好'} {vis}km\n"
        f"紫外线: {'弱' if uv_index <= 2 else '较弱' if uv_index <= 4 else '一般' if uv_index <= 6 else '较强' if uv_index <= 9 else '强'} {uv_index}mW/m2"
    )
    safety = ""
    if precip > 5:
        safety += "\n~雨天路滑, 记得带伞~"
    if temp_max <= 5:
        safety += "\n~天气寒冷, 注意保暖~"
    if vis <= 10:
        safety += "\n~能见度差, 小心出行~"
    if uv_index >= 10:
        safety += "\n~紫外线强, 注意防晒~"
    if humidity <= 10:
        safety += "\n~天气干燥, 注意补水~"
    content += safety

    return content


from collections import deque

# 全局速率限制器 - 所有请求共享
_rate_limiter_calls = deque()
_rate_limiter_max_calls = 3
_rate_limiter_period = 1.0


def rate_limited_request(url, headers, timeout=5):
    """
    带速率限制的请求函数
    确保每秒最多发送3次请求
    """
    global _rate_limiter_calls

    now = time.time()

    # 移除过期的调用记录(超过1秒的)
    while _rate_limiter_calls and _rate_limiter_calls[0] <= now - _rate_limiter_period:
        _rate_limiter_calls.popleft()

    # 如果已达到速率限制,等待到最早的请求过期
    if len(_rate_limiter_calls) >= _rate_limiter_max_calls:
        sleep_time = _rate_limiter_period - (now - _rate_limiter_calls[0])
        if sleep_time > 0:
            print(f"[速率限制] 等待 {sleep_time:.2f} 秒...")
            time.sleep(sleep_time)
            now = time.time()
            # 再次清理过期记录
            while (
                _rate_limiter_calls
                and _rate_limiter_calls[0] <= now - _rate_limiter_period
            ):
                _rate_limiter_calls.popleft()

    # 记录本次请求时间
    _rate_limiter_calls.append(now)

    # 发起实际请求
    return requests.get(url, headers, timeout=timeout)


def wrapper_tian_jv_shu_xing(func):
    """
    装饰器\n
    包装函数, 包装网络请求, 传入网址, 装饰器获取返回值提交原函数\n
    完善报错信息\n
    """

    def wrapper(url):
        try:
            result = rate_limited_request(
                url, headers=get_random_ua(), timeout=5
            ).json()
            return (
                func(result)
                .replace("\u3000", " ")
                .replace("\t", " ")
                .replace("\u0020", " ")
            )
        except Exception as e:
            print(f"[err] plugins.cmdTimeReminder.get.wrapper_tian_jv_shu_xing: {e}")
            return "-1"

    return wrapper


def get_news() -> list[str]:
    """获取当日新闻摘要, 若报错则返回 '-1'"""
    function_urls = [
        f"https://api.1314.cool/getbaiduhot/",
        f"https://apis.tianapi.com/nethot/index?key={tian_jv_shu_xing_api3}",
        # f"https://api.qqsuu.cn/api/dm-weibohot?apiKey=ff4fdf26deff8ee31fd231df243dae47",
        f"https://apis.tianapi.com/bulletin/index?key={tian_jv_shu_xing_api1}",
    ]

    # api失效
    @wrapper_tian_jv_shu_xing
    def getbaiduhot(result: str) -> str:
        """1.百度热搜 每三分钟实时更新"""
        getbaiduhot_content = "~~~1.今日热点~~~" + "".join(
            [f'\n{i+1}. {item["word"]}' for i, item in enumerate(result["data"][:15])]
        )
        return getbaiduhot_content

    @wrapper_tian_jv_shu_xing
    def nethot(result: str) -> str:
        """1.天聚数行 百度热搜榜"""
        nethot_content = "~~~2.今日热点~~~" + "".join(
            [
                f'\n\n{i+1}. {item["keyword"]}'
                + (
                    f'\n  ->{item["brief"].replace("查看更多&gt;", "").strip()}'
                    if item["brief"] != "查看更多&gt;"
                    else ""
                )
                for i, item in enumerate(result["result"]["list"][:15])
            ]
        )
        return nethot_content

    @wrapper_tian_jv_shu_xing
    def api(result: str) -> str:
        """2.大米api - 免费APi"""
        new2_content = "~~~2.今日热点~~~\n" + "\n".join(
            [
                f"{i+1}. {new2_item['hotword']}"
                for i, new2_item in enumerate(result["data"]["list"][:15])
            ]
        )
        return new2_content

    @wrapper_tian_jv_shu_xing
    def bulletin(result: str) -> str:
        """3.天聚数行 新闻 推送"""
        result = result["result"]["list"]
        bulletin_content = f"~~~3.今日热点~~~\n{result[0]['mtime']}\n"
        bulletin_content += "\n".join(
            f"{i+1}. {new3_item['title']}" for i, new3_item in enumerate(result[:15])
        )
        return bulletin_content

    results = []
    for url in function_urls:
        function_name = url.split("/")[3]
        if function_name in locals():
            function = locals()[function_name]
            result = function(url)
            results.append(result)
        else:
            results.append(f"err: get.get_news() 找不到 [{function_name}] 函数!!!")

    return results


def get_day_night() -> list[str]:
    """list[0] == '早安' list[1] == '晚安', 若报错则返回 '-1'"""

    @wrapper_tian_jv_shu_xing
    def zaoan(result: str) -> str:
        """天聚数行 早安心语"""
        zaoan_content = "[bot] ~早安心语~\n" + result["result"]["content"]
        return zaoan_content

    @wrapper_tian_jv_shu_xing
    def wanan(result: str) -> str:
        """天聚数行 晚安心语"""
        wanan_content = "[bot] ~晚安心语~\n" + result["result"]["content"]
        return wanan_content

    return [
        zaoan(f"https://apis.tianapi.com/zaoan/index?key={tian_jv_shu_xing_api1}"),
        wanan(f"https://apis.tianapi.com/wanan/index?key={tian_jv_shu_xing_api1}"),
    ]


def get_sentences_per_day() -> list[str]:
    """获取每日语句, 若报错则返回 '-1'"""
    function_urls = [
        f"https://apis.tianapi.com/pyqwenan/index?key={tian_jv_shu_xing_api1}",
        f"https://apis.tianapi.com/hsjz/index?key={tian_jv_shu_xing_api1}",
        f"https://apis.tianapi.com/dialogue/index?key={tian_jv_shu_xing_api1}",
        f"https://apis.tianapi.com/tiangou/index?key={tian_jv_shu_xing_api1}",
        f"https://apis.tianapi.com/hotreview/index?key={tian_jv_shu_xing_api1}",
        f"https://apis.tianapi.com/dujitang/index?key={tian_jv_shu_xing_api1}",
        f"https://apis.tianapi.com/caihongpi/index?key={tian_jv_shu_xing_api2}",
        f"https://apis.tianapi.com/one/index?key={tian_jv_shu_xing_api2}",
        f"https://apis.tianapi.com/proverb/index?key={tian_jv_shu_xing_api2}",
        f"https://apis.tianapi.com/riddle/index?key={tian_jv_shu_xing_api2}",
        f"https://apis.tianapi.com/mingyan/index?key={tian_jv_shu_xing_api2}",
        f"https://apis.tianapi.com/saylove/index?key={tian_jv_shu_xing_api2}",
        f"https://apis.tianapi.com/skl/index?key={tian_jv_shu_xing_api2}",
        f"https://apis.tianapi.com/godreply/index?key={tian_jv_shu_xing_api2}",
        f"https://apis.tianapi.com/xiehou/index?key={tian_jv_shu_xing_api2}",
        f"https://apis.tianapi.com/joke/index?key={tian_jv_shu_xing_api2}",
    ]

    @wrapper_tian_jv_shu_xing
    def pyqwenan(result: str) -> str:
        """1.天聚数行 朋友圈文案"""
        pyqwenan_content = f"~~1.朋友圈文案~~\n{result['result']['content']}"
        pyqwenan_content += (
            f"\n——  {result['result']['source']}"
            if result["result"]["source"] != "佚名"
            else ""
        )
        return pyqwenan_content

    @wrapper_tian_jv_shu_xing
    def hsjz(result: str) -> str:
        """2.天聚数行 失恋分手文案"""
        hsjz_content = f"~~2.失恋分手文案~~\n{result['result']['content']}"
        return hsjz_content

    @wrapper_tian_jv_shu_xing
    def dialogue(result: str) -> str:
        """3.天聚数行 经典台词"""
        dialogue_chinese = result["result"]["dialogue"]
        dialogue_english = result["result"]["english"]
        if dialogue_chinese and dialogue_english:
            dialogue_content = f"~~3.经典台词~~\n中文: {dialogue_chinese}"
            dialogue_content += f"\n英文: {dialogue_english}"
        else:
            dialogue_content = f"~~3.经典台词~~\n  ->{dialogue_chinese if dialogue_chinese else dialogue_english}"
        dialogue_content += f"\n——《{result['result']['source']}》"
        return dialogue_content

    @wrapper_tian_jv_shu_xing
    def tiangou(result: str) -> str:
        """4.天聚数行 舔狗日记"""
        tiangou_content = f"~~4.舔狗日记~~\n{result['result']['content']}"
        return tiangou_content

    @wrapper_tian_jv_shu_xing
    def hotreview(result: str) -> str:
        """5.天聚数行 云音乐热评"""
        hotreview_content = f"~~5.云音乐热评~~\n{result['result']['content']}"
        hotreview_content += f"\n——  {result['result']['source']}"
        return hotreview_content

    @wrapper_tian_jv_shu_xing
    def dujitang(result: str) -> str:
        """6.天聚数行 毒鸡汤"""
        dujitang_content = f"~~6.毒鸡汤~~\n{result['result']['content']}"
        return dujitang_content

    @wrapper_tian_jv_shu_xing
    def caihongpi(result: str) -> str:
        """7.天聚数行 彩虹屁"""
        caihongpi_content = f"~~7.彩虹屁~~\n{result['result']['content']}"
        return caihongpi_content

    @wrapper_tian_jv_shu_xing
    def one(result: str) -> str:
        """8.天聚数行 ONE一个"""
        one_content = f"~~8.ONE一个~~\n{result['result']['word']}"
        one_content += (
            f"\n——《{result['result']['wordfrom']}》"
            if result["result"]["wordfrom"]
            else ""
        )
        return one_content

    @wrapper_tian_jv_shu_xing
    def proverb(result: str) -> str:
        """9.天聚数行 文化谚语"""
        proverb_content = f"~~9.文化谚语~~\n{result['result']['front']}"
        proverb_content += f"\n{result['result']['behind']}"
        return proverb_content

    @wrapper_tian_jv_shu_xing
    def riddle(result: str) -> str:
        """10.天聚数行 谜语大全"""
        riddle_content = f"~~10.谜语大全~~\n问题: {result['result']['quest']}"
        riddle_content += f"\n答案: {result['result']['answer']}"
        return riddle_content

    @wrapper_tian_jv_shu_xing
    def mingyan(result: str) -> str:
        """11.天聚数行 名人名言"""
        mingyan_content = f"~~11.名人名言~~\n{result['result']['list'][0]['content']}"
        mingyan_content += f"\n——  {result['result']['list'][0]['author']}"
        return mingyan_content

    @wrapper_tian_jv_shu_xing
    def saylove(result: str) -> str:
        """12.天聚数行 土味情话"""
        saylove_content = f"~~12.土味情话~~\n{result['result']['content']}"
        return saylove_content

    @wrapper_tian_jv_shu_xing
    def skl(result: str) -> str:
        """13.天聚数行 顺口溜"""
        skl_content = f"~~13.顺口溜~~\n{result['result']['content']}"
        return skl_content

    @wrapper_tian_jv_shu_xing
    def godreply(result: str) -> str:
        """14.天聚数行 神回复"""
        godreply_content = (
            f"~~14.神回复~~\n评论: {result['result']['list'][0]['title']}"
        )
        godreply_content += f"\n回复: {result['result']['list'][0]['content']}"
        return godreply_content

    @wrapper_tian_jv_shu_xing
    def xiehou(result: str) -> str:
        """15.天聚数行 歇后语"""
        xiehou_content = f"~~15.歇后语~~\n{result['result']['list'][0]['quest']}"
        xiehou_content += f"\n  ->{result['result']['list'][0]['result']}"
        return xiehou_content

    @wrapper_tian_jv_shu_xing
    def joke(result: str) -> str:
        """16.天聚数行 雷人笑话"""
        joke_content = f"~~16.雷人笑话~~\n[{result['result']['list'][0]['title']}]"
        joke_content += f"\n  ->{result['result']['list'][0]['content']}"
        return joke_content

    results = []
    for url in function_urls:
        function_name = url.split("/")[3]
        if function_name in locals():
            function = locals()[function_name]
            result = function(url)
            results.append(result)
        else:
            results.append(
                f"err: get.get_sentences_per_day() 找不到 [{function_name}] 函数!!!"
            )

    return results


@cache_with_time_limit
def fanyi(text: str, to: str = "jp") -> str:
    """
    翻译字符串, 若报错则返回原字符串\n
    请注意此项目为计次收费, 谨慎使用！！！
    """
    text_list = text.split("\n")
    fanyi_url = "https://apis.tianapi.com/fanyi/index"
    try:
        fanyi_content = ""
        for line in text_list:
            params = {"key": tian_jv_shu_xing_api3, "text": line, "to": to}
            fanyi_result = requests.post(fanyi_url, data=params).json()
            fanyi_content += fanyi_result["result"]["dst"] + "\n"
    except:
        return f"[warning] 翻译失败!\n{text}"

    return fanyi_content.rstrip("\n")


@cache_with_time_limit
def get_area(area: str) -> str:
    """获取ip对应物理地址, 若报错则返回 '-1'"""
    area_url = (
        f"https://apis.tianapi.com/ipquery/index?key={tian_jv_shu_xing_api3}&ip={area}"
    )
    try:
        area_result = requests.get(area_url, headers=get_random_ua()).json()
        area_result = area_result["result"]
        area_content = f"地区: {area_result['continent']} {area_result['country']} {area_result['province']}"
        if area_result["province"] != area_result["city"]:
            area_content += f" {area_result['city']}"
        area_content += "\n"
        area_content += (
            f"区域: {area_result['district']}\n"
            if area_result["district"] != ""
            else ""
        )
        area_content += (
            f"运营商: {area_result['isp']}\n" if area_result["isp"] != "" else ""
        )
        area_content += f"经纬度: {area_result['longitude']}, {area_result['latitude']}"

    except:
        area_url = f"http://whois.pconline.com.cn/ipJson.jsp?ip={area}&json=true"
        try:
            area_result = requests.get(area_url, headers=get_random_ua()).json()
            area_content = ""
            if area_result["pro"] != "":
                area_content += f"地区: {area_result['pro']} {area_result['city']}\n"
            network_provider = (
                area_result["addr"]
                .replace(area_result["pro"], "")
                .replace(area_result["city"], "")
                .strip()
            )
            area_content += f"运营商: {network_provider}"

        except:
            return "-1"

    return area_content


def add_datetime(
    converted_datetime, years=0, months=0, days=0, hours=0, minutes=0, seconds=0
):
    """日期进位算法"""
    datetime_obj = datetime.fromtimestamp(time.mktime(converted_datetime))
    month_overflow = (datetime_obj.month - 1 + months) // 12
    new_year = datetime_obj.year + years + month_overflow
    new_month = ((datetime_obj.month - 1 + months) % 12) + 1
    max_day = calendar.monthrange(new_year, new_month)[1]
    new_day = min(datetime_obj.day, max_day) + days

    while new_day > max_day:
        new_day -= max_day
        new_month += 1
        if new_month > 12:
            new_month = 1
            new_year += 1
        max_day = calendar.monthrange(new_year, new_month)[1]

    new_datetime = datetime(
        new_year,
        new_month,
        new_day,
        datetime_obj.hour,
        datetime_obj.minute,
        datetime_obj.second,
    )
    new_datetime += timedelta(hours=hours, minutes=minutes, seconds=seconds)

    return new_datetime.timetuple()


def get_file_hash(file_path):
    """计算文件的哈希值"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def remove_empty_paths(paths):
    """嵌套列表/字典去空"""
    if isinstance(paths, list):
        return [remove_empty_paths(path) for path in paths if remove_empty_paths(path)]
    elif isinstance(paths, dict):
        return {
            key: remove_empty_paths(value)
            for key, value in paths.items()
            if remove_empty_paths(value)
        }
    else:
        return paths


def equals(a: dict, b: dict):
    """检查两个日志是否相等, 忽略`check_status`和`isNew`字段"""
    keys_to_ignore = ["check_status", "isNew"]

    for key, value_a in a.items():
        if key in keys_to_ignore:
            continue
        value_b = b.get(key)
        if value_a != value_b:
            return False

    return True


def web_logs():
    """网站日志检测"""
    root_log_path = r"C:\wwwroot\backend\logs\{date}.json"
    today_date_string = datetime.now().strftime("%Y-%m-%d")
    yesterday_date_string = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    today_bt_log_path = root_log_path.format(date=today_date_string)
    yesterday_bt_log_path = root_log_path.format(date=yesterday_date_string)
    today_hash_logs_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "today_hash_logs.txt"
    )

    # 计算本地文件的哈希值
    if os.path.exists(today_bt_log_path):
        local_hash = get_file_hash(today_bt_log_path)
    elif os.path.exists(yesterday_bt_log_path):
        local_hash = get_file_hash(yesterday_bt_log_path)
    else:
        return

    # 通过哈希值比较文件是否发生改变
    with open(today_hash_logs_path, "r") as tmp_file:
        today_hash = tmp_file.read().strip()

    # 如果哈希值没有发生改变，直接返回
    if local_hash == today_hash:
        return
    with open(today_hash_logs_path, "w") as tmp_file:
        tmp_file.write(local_hash)

    merged_json = []
    """今天和昨天文件内容"""
    if os.path.exists(yesterday_bt_log_path):
        with open(yesterday_bt_log_path, "r", encoding="utf-8") as yesterday_file:
            tmp_json = json.loads(yesterday_file.read())
            for tmp in tmp_json:
                tmp["check_status"] = yesterday_date_string
            merged_json += tmp_json
    if os.path.exists(today_bt_log_path):
        with open(today_bt_log_path, "r", encoding="utf-8") as today_file:
            tmp_json = json.loads(today_file.read())
            for tmp in tmp_json:
                tmp["check_status"] = today_date_string
            merged_json += tmp_json

    # 无内容直接返回
    if not merged_json:
        return

    today_json = []
    """暂存文件内容(即已经上报过的内容)"""
    today_logs_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "today_logs.json"
    )
    with open(today_logs_path, "r+", encoding="utf-8") as file:
        today_json = json.loads(file.read())
    today_json = [
        tmp
        for tmp in today_json
        if tmp.get("check_status") in [today_date_string, yesterday_date_string]
    ]

    reply = []
    has_new_visitor = "\n全部访客已离开"  # 如果有新访客，给出提示语
    today_json_length = len(today_json)
    for index in range(len(merged_json)):
        if index >= today_json_length or not (  # 大于下标的一定需要报
            # 相同不需要报
            equals(merged_json[index], today_json[index])
            # 新访客只报第一次
            or (
                not merged_json[index]["logoutTime"]
                and today_json[index].get("isNew") == "no"
            )
        ):
            log = merged_json[index]
            tmp_rep = f"IP: {log['ip']}\n"
            tmp = get_area(log["ip"])
            if tmp == "-1":
                tmp = "地区: 查询失败!!!\n"
            else:
                tmp += "\n"
            tmp_rep += tmp
            tmp_rep += f"用户: {log['username']}"
            if len(log["password"]) > 4:  # 排除null的情况
                tmp_rep += f" ({log['password'][:2] + '*' * (len(log['password']) - 3) + log['password'][-1]})\n"
            else:
                tmp_rep += f" ({log['password']})\n"
            tmp_rep += f"登入时间: [{log['loginTime']}]"
            if not log["logoutTime"]:
                tmp = "访客进入\n"
                tmp += tmp_rep
                reply.append(tmp)
                merged_json[index]["isNew"] = "no"  # 已经上报，但访客未离开
                has_new_visitor = "\n有访客游览中..."
            else:
                tmp = "访客已离开\n"
                tmp += tmp_rep
                tmp += f"\n离开时间: [{log['logoutTime']}]\n"
                tmp += f"浏览路线: {pformat(remove_empty_paths(log['visitedPaths']), width=80)}"
                reply.append(tmp)
        elif (
            index < today_json_length
            and not merged_json[index]["logoutTime"]
            and today_json[index].get("isNew") == "no"
        ):
            merged_json[index]["isNew"] = "no"  # 同步之前的数据
            if merged_json[index]["check_status"] == today_date_string:
                has_new_visitor = "\n有访客游览中..."

    # 存在访客在但已经上报过的情况 导致哈希改变，故此处可能不需要上报
    with open(today_logs_path, "w", encoding="utf-8") as file:
        file.write(json.dumps(merged_json, indent=2, ensure_ascii=False))
    if len(reply) == 0:
        return

    for i in range(len(reply)):
        reply[i] = f"编号: [{i+1}] {reply[i]}"
    reply[0] = f"[bot] 检测到网站有新访客~{has_new_visitor}\n\n{reply[0]}"

    return reply


def sent_api_daily_notes(cqhttp: CQHTTP_Protocol, my_qq_number: int):
    """发送api简报"""
    file_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "api_daily_notes.txt"
    )
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read().strip()
    cqhttp.sendPersonMessage(my_qq_number, content)


def check_internet_status(cqhttp: CQHTTP_Protocol, my_qq_number: int) -> None:
    """检测寝室电脑联网状态"""
    file_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "morning_internet_status.txt"
    )

    try:
        with open(file_path, "r") as file:
            content = file.read().strip()

        current_date = datetime.now().strftime("%Y-%m-%d")
        if content == current_date:
            # cqhttp.sendPersonMessage(my_qq_number, "[bot] 机革成功连接到互联网~")
            sent_api_daily_notes(cqhttp, my_qq_number)
        else:
            cqhttp.sendPersonMessage(
                my_qq_number, "[bot]err: 机革未自动连接到互联网！！！"
            )
            try:
                from Models.Plugins import Plugin
                from Events import GetWCF__, GetConfig__

                my_wx_id = Plugin.emit(GetConfig__).my_wx_id
                wcf = Plugin.emit(GetWCF__)
                if wcf:
                    wcf.send_text("[bot]err: 机革未自动连接到互联网！！！", my_wx_id)
            except Exception as e:
                import logging

                logging.error(f"机革未自动连接到互联网时发生错误：{e}")

    except Exception as e:
        cqhttp.sendPersonMessage(
            my_qq_number, f"[bot]err: 寝室电脑联网检测错误！！！{e}"
        )

    return
